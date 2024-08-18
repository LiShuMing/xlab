package com.starrocks.itest.framework.schema

import com.starrocks.itest.framework.utils.RandUtil
import com.starrocks.itest.framework.utils.Util

enum class TableType {
    DUPLICATE,
    AGGREGATE,
    UNIQUE,
    PRIMARY,
}

class Table(
    val tableName: String,
    val fields: List<Field>,
    val keyLimit: Int,
    val bucketNum: Int = 1,
    val tableType: TableType = TableType.DUPLICATE
) {
    companion object {
        data class Key(val type: TableType, val keys: List<String>)

        data class Partition(val field: String, val start: String, val end: String, val interval: Int)

        data class Bucket(val bucketNum: Int, val keys: List<String>)

        data class Property(val key: String, val value: String)

        data class Properties(val keyValues: List<Property>)
    }

    var replicaFactor: Int = 1
    var key: Key? = Key(tableType, fields.take(keyLimit).map { it.name }.toList())
    var partition: Partition? = null
    var bucket: Bucket? = Bucket(bucketNum, key!!.keys)
    var properties: Properties? = Properties(
        listOf(
            Property("replication_num", "$replicaFactor"),
            Property("in_memory", "false"),
            Property("storage_format", "default")
        )
    )

    fun field(name: String): Field {
        return fields.first { it.name == name }
    }

    fun simpleFields(): List<SF> = fields.map { f -> f.simple() }

    fun byKeys(tuples: List<List<String>>, cb: (List<String>) -> String): List<String> {
        return tuples.map { t ->
            val keyPred = Util.zip(t, keyFields()).joinToString(" and ") { (v, f) -> "${f.name} = '$v'" }
            val prefix = cb(t.drop(keyFields().size))
            "$prefix where $keyPred"
        }
    }

    fun deleteByKeys(tuples: List<List<String>>): List<String> {
        return byKeys(tuples) { _ ->
            "delete from $tableName"
        }
    }

    fun updateByKeys(tuples: List<List<String>>): List<String> {
        return byKeys(tuples) { values ->
            val assigments =
                Util.zip(values, fields.drop(keyFields().size)).joinToString(", ") { (v, f) -> "${f.name} = '$v'" }
            "update $tableName set $assigments"
        }
    }

    fun partialUpdateByKeys(tuples: List<List<String>>): List<String> {
        val valueFields = valueFields(emptySet())
        val randNumValues = RandUtil.generateRandomRangeInt(1, valueFields.size)
        return byKeys(tuples) { values ->
            val assigments = Util.zip(values, valueFields).shuffled().take(randNumValues())
                .joinToString(", ") { (v, f) -> "${f.name} = '$v'" }
            "update $tableName set $assigments"
        }
    }

    fun sql(): String {
        val fieldDefs = fields.map { it.sql() }
        val template = "table.template"
        return Util.renderTemplate(
            template,
            "tableName" to tableName,
            "fieldDefs" to fieldDefs,
            "key" to key,
            "bucket" to bucket,
            "partition" to partition,
            "properties" to properties
        )
    }

    fun setKey(type: TableType, keys: List<String>): Table {
        this.key = Key(type, keys)
        return this
    }
    fun setKey(type: TableType): Table {
        this.key = Key(type, this.keyFields().map{kf->kf.name})
        return this
    }

    fun relation(): Pair<String, List<SF>> {
        return tableName to fields.map { f -> f.simple() }
    }

    fun setPartition(field: String, start: String, end: String): Table {
        this.partition = Partition(field, start, end, 1)
        return this
    }

    fun setBucket(bucketNum: Int, keys: List<String>): Table {
        this.bucket = Bucket(bucketNum, keys)
        return this
    }

    fun addProperty(key: String, value: String): Table {
        this.properties = Properties(this.properties!!.keyValues + Property(key, value))
        return this
    }
    fun setColocateWith(colocateGroup: String): Table {
        return addProperty("colocate_with", colocateGroup)
    }

    fun setProperty(properties: Properties): Table {
        this.properties = properties
        return this
    }

    fun clone_extra(t: Table): Table {
        this.partition = t.partition
        this.bucket = t.bucket
        this.properties = t.properties
        return this
    }

    fun alterTable(db: String, field: Field): Pair<String?, Table> {
        var alterStmt: String? = null
        val changedFields = fields.map { f ->
            if (f.name == field.name) {
                alterStmt = "ALTER TABLE $db.$tableName MODIFY COLUMN ${field.sql()};"
                field
            } else {
                f
            }
        }
        return (alterStmt to Table(tableName, changedFields, keyLimit))
    }

    fun showAlterTableColumnSql(): String {
        return "SHOW ALTER TABLE COLUMN WHERE TableName = '$tableName' ORDER BY CreateTime DESC LIMIT 1"
    }

    fun selectAll() = "select * from $tableName"

    fun keyFields(): List<Field> {
        val keySet = key!!.keys.toSet()
        return fields.filter { keySet.contains(it.name) }.toList()
    }

    fun valueFields(excludes: Set<String>): List<Field> {
        val keySet = key!!.keys.toSet()
        return fields.filter { !keySet.contains(it.name) && !excludes.contains(it.name) }.toList()
    }

    fun nullableTable(nullRatio: Int): Table {
        val toNullable: (Field) -> Field = { f ->
            when (f) {
                is SF -> CF.nullable(f, nullRatio)
                is CF -> CF.nullable(f.fld, nullRatio)
                is AggregateField -> AggregateField(CF.nullable(f.fld.fld, nullRatio), f.aggType)
            }
        }
        return Table(tableName, fields.map(toNullable), keyLimit, bucketNum, tableType).clone_extra(this)
    }
    fun nullableTable() = nullableTable(50)

    fun notNullableTable(): Table {
        val toNotNullable: (Field) -> Field = { f ->
            when (f) {
                is SF -> f
                is CF -> f.fld
                is AggregateField -> AggregateField.aggregate(CF.trivial(f.fld.fld), f.aggType)
            }
        }
        return Table(tableName, fields.map(toNotNullable), keyLimit, bucketNum, tableType)
    }

    fun aggregateTable(aggTypes: List<AggregateType>): Table {
        val nextAggType = Util.roundRobin(aggTypes)
        val toReplace: (Field) -> Field = { f ->
            when (f) {
                is SF -> AggregateField.aggregate(CF.trivial(f), nextAggType())
                is CF -> AggregateField.aggregate(f, nextAggType())
                is AggregateField -> AggregateField.aggregate(f.fld, nextAggType())
            }
        }

        val toNoneAggregate: (Field) -> Field = { f ->
            when (f) {
                is AggregateField -> f.fld
                else -> f
            }
        }

        var t = Table(
            tableName,
            keyFields().map(toNoneAggregate) + valueFields(emptySet()).map(toReplace),
            keyLimit,
            bucketNum,
            TableType.AGGREGATE
        )
        t.clone_extra(this)
        return t
    }

    fun insertIntoFromTableSql(srcTableName: String, sample: Double, vararg columMapping: Pair<SF, SF>): String {
        val columnNames = this.fields.joinToString(", ") { f -> f.name }
        val insertTableSql = "INSERT INTO $tableName ($columnNames)"
        val selectItems = columMapping.joinToString(", ") { (fs, fd) -> fs.castTo(fd) }
        val selectSql = "SELECT  $selectItems FROM $srcTableName WHERE rand() <= $sample"
        return "$insertTableSql $selectSql";
    }

    fun addPartition(name: String, start: String, end: String) = addPartition(name, start, end, 1)
    fun addPartition(name: String, start: String, end: String, interval: Int): Table? {
        val f = fields.filter { f ->
            f.name == name
        }.first()
        val isTimeType = when (f) {
            is FixedLengthField -> f.type == FixedLengthType.TYPE_DATE || f.type == FixedLengthType.TYPE_DATETIME
            else -> false
        }
        if (!isTimeType) {
            return null
        }
        val table = Table(tableName, fields, keyLimit, bucketNum, tableType)
            .setBucket(bucket!!.bucketNum, bucket!!.keys)
        table.partition = Partition(name, start, end, interval)
        return table
    }

    fun uniqueTable(): Table {
        val toNoneAggregate: (Field) -> Field = { f ->
            when (f) {
                is AggregateField -> f.fld
                else -> f
            }
        }
        return Table(tableName, fields.map(toNoneAggregate), keyLimit, bucketNum, TableType.UNIQUE)
    }

    fun duplicateTable(): Table {
        val toNoneAggregate: (Field) -> Field = { f ->
            when (f) {
                is AggregateField -> f.fld
                else -> f
            }
        }
        return Table(tableName, fields.map(toNoneAggregate), keyLimit, bucketNum, TableType.DUPLICATE).setReplicaFactor(
            this.replicaFactor
        )
    }

    fun resetKeyLimit(newKeyLimit: Int) = Table(tableName, fields, newKeyLimit, bucketNum, tableType)

    fun renameTable(newTableName: String) =
        Table(newTableName, fields, keyLimit, bucketNum, tableType).clone_extra(this)

    fun setReplicaFactor(rn: Int): Table {
        val tab = Table(tableName, fields, keyLimit, bucketNum, tableType).clone_extra(this)
        tab.replicaFactor = rn
        tab.properties = Properties(tab.properties!!.keyValues.map { (k, v) ->
            Property(
                k,
                if (k == "replication_num") {
                    "$rn"
                } else {
                    v
                }
            )
        })
        return tab
    }
}
