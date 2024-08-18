package com.starrocks.itest.framework.mv

import com.google.common.base.Joiner
import com.google.common.base.Preconditions
import com.google.common.base.Strings
import com.google.common.collect.Lists
import com.starrocks.schema.MMaterializedView

class PartitionByBlock(val partExpression: String) : Block
class DistributedByBlock(val distDesc: String) : Block
class OrderByBlock(val orderByExpression: String) : Block
class RefreshSchemaBlock(val refreshMoment:String, val refreshSchema: String) : Block
class PropertiesBlock(val properties: List<String>, val isPartitionMV: Boolean) : Block

// How to refresh the mv
class RefreshActionBlock(startPartition: String, endPartition: String) : Block;

class PartitionByWorker(val mv: MMaterializedView) : Worker {
    override fun buildBlocks(): List<Block> {
        val result = if (mv.isMinified) {
            arrayListOf()
        } else {
            arrayListOf(
                // no partition
                PartitionByBlock(""),
            )
        }

        // TODO: Distinguish partCol's data type.
        if (!Strings.isNullOrEmpty(mv.partCol) && !mv.partCol.contains("str2date") &&
            setOf("date", "datetime").contains(mv.partColumnType)
        ) {
            // with partition key
            result.add(PartitionByBlock(partExpression = mv.partCol));
            // with partition expression
            result.add(PartitionByBlock(partExpression = "date_trunc('day', ${mv.partCol})"))
            // how to distinguish str2date
        } else {
            // with partition key
            result.add(PartitionByBlock(partExpression = mv.partCol));
            // how to distinguish str2date
        }
        return result
    }
}

class DistributedByWorker(val mv: MMaterializedView) : Worker {
    val distCol = mv.distCol
    override fun buildBlocks(): List<Block> {
        if (Strings.isNullOrEmpty(distCol)) {
            return listOf(
                // no distribution key
                DistributedByBlock("DISTRIBUTED BY RANDOM"),
            )
        } else {
            if (mv.isMinified) {
                return listOf(
                    // with distribution key with buckets
                    DistributedByBlock("DISTRIBUTED BY HASH(${distCol}) BUCKETS 3"),
                )
            } else {
                return listOf(
                    // no distribution key
                    DistributedByBlock("DISTRIBUTED BY RANDOM"),
                    // with distribution key without buckets
                    DistributedByBlock("DISTRIBUTED BY HASH(${distCol})"),
                    // with distribution key with buckets
                    DistributedByBlock("DISTRIBUTED BY HASH(${distCol}) BUCKETS 3"),
                )
            }
        }
    }
}

class OrderByWorker(val mv: MMaterializedView) : Worker {
    val orderKeys = mv.orderKeys
    override fun buildBlocks(): List<Block> {
        if (Strings.isNullOrEmpty(orderKeys)) {
            return listOf(
                OrderByBlock(orderByExpression = "")
            )
        } else {
            if (mv.isMinified) {
                return listOf(
                    OrderByBlock(orderByExpression = orderKeys),
                )
            } else {
                return listOf(
                    OrderByBlock(orderByExpression = ""),
                    OrderByBlock(orderByExpression = orderKeys),
                )
            }
        }
    }
}

class RefreshSchemaWorker(val mv:MMaterializedView) : Worker {
    val refreshMoment = "DEFERRED"
    override fun buildBlocks(): List<Block> {
        if (Strings.isNullOrEmpty(mv.refreshSchema) || mv.refreshSchema?.equals("MANUAL") == true) {
            return listOf(RefreshSchemaBlock("${refreshMoment}", "MANUAL"))
        } else {
            return listOf(RefreshSchemaBlock("${refreshMoment}", "ASYNC ${mv.refreshSchema}"))
        }
    }
}

class PropertiesWorker(val mv: MMaterializedView) : Worker {
    override fun buildBlocks(): List<Block> {
        val nonPartitionMVProperties = listOf(
            "'replication_num'='1'",
            "'force_external_table_query_rewrite'='true'",
        )
        val partitionMVProperties = listOf(
             "'partition_ttl_number'='10'",
            "'partition_refresh_number'='-1'", // should not be equal with default value
        )
        val mvDefaultProperties = if (mv.mvProperties == null || mv.mvProperties.isEmpty()) {
            emptyList<String>()
        } else {
            mv.mvProperties
        }
        val finalProperties = nonPartitionMVProperties.toMutableList()
        finalProperties.addAll(mvDefaultProperties)

        val result = mutableListOf(PropertiesBlock(properties = finalProperties, false))
        if (mv.isMinified) {
           return result
        } else {
            val newProperties = finalProperties.toMutableList()
            newProperties.addAll(partitionMVProperties)
            result.add(PropertiesBlock(properties = newProperties, true))
            return result
        }
    }
}

class MVBlock(val mv: MMaterializedView,
              val partByBlock: PartitionByBlock,
              val distByBlock: DistributedByBlock,
              val orderByBlock: OrderByBlock,
              val refreshBlock: RefreshSchemaBlock,
              val propertiesBlock: PropertiesBlock) {
    private var mvName: String = mv.tableName

    fun isValid(): Boolean {
        if (propertiesBlock.isPartitionMV && Strings.isNullOrEmpty(partByBlock.partExpression)) {
            return false;
        }
        return true;
    }

    fun withName(mvName: String): MVBlock {
        this.mvName = mvName
        return this
    }

    fun generateCreateSql(): String {
        var sql = String.format("CREATE MATERIALIZED VIEW if not exists %s \n", mvName)

        // distribute desc
        sql += distByBlock.distDesc + "\n"

        // refresh schema
        sql += "REFRESH ${refreshBlock.refreshMoment} ${refreshBlock.refreshSchema} \n"
        // partition expression
        if (!Strings.isNullOrEmpty(partByBlock.partExpression)) {
            sql += String.format("PARTITION BY %s \n", partByBlock.partExpression)
        }
        if (!Strings.isNullOrEmpty(orderByBlock.orderByExpression)) {
            sql += String.format("ORDER BY (%s) \n", orderByBlock.orderByExpression)
        }
        sql += "PROPERTIES (\n" +
                Joiner.on(",\n").join(propertiesBlock.properties) +
                "\n) "
        sql += String.format("AS \n %s;", mv.definedQuery)
        return sql
    }
}

class MVWorker(val mv: MMaterializedView) {
    val subWorkers = listOf(
        PartitionByWorker(mv),
        DistributedByWorker(mv),
        OrderByWorker(mv),
        RefreshSchemaWorker(mv),
        PropertiesWorker(mv),
    )

    fun getPermutations(onlyPartition: Boolean = false): List<MVBlock> {
        val subBlockSets = mutableListOf<List<Block>>()
        for (subWork in subWorkers)  {
            subBlockSets.add(subWork.buildBlocks())
        }

        val rounds = Lists.cartesianProduct(subBlockSets)
        val mvBlocks = mutableListOf<MVBlock>()
        for (round in rounds) {
            Preconditions.checkArgument(round.size == subWorkers.size)
            val mvBlock = MVBlock(
                mv,
                (round[0]) as PartitionByBlock,
                round[1] as DistributedByBlock,
                round[2] as OrderByBlock,
                round[3] as RefreshSchemaBlock,
                round[4] as PropertiesBlock,
            )
            if (onlyPartition && Strings.isNullOrEmpty(mvBlock.partByBlock.partExpression)) {
                continue
            }
            if (!mvBlock.isValid()) {
                continue
            }
            mvBlocks.add(mvBlock)
        }
        return mvBlocks
    }
}