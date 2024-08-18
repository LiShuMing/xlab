package com.starrocks.itest.framework.mv

enum class ColumnTypeEnum {
    STRING,
    NUMBER,
    DATETIME,
    BITMAP,
    HLL,
    PERCENTILE,
    ALL
}

class Enumerator {
    companion object {
        val aggFuncs: Map<String, Array<ColumnTypeEnum>> = mapOf(
            "sum(<col>)" to arrayOf(ColumnTypeEnum.NUMBER),
            "min(<col>)" to arrayOf(ColumnTypeEnum.NUMBER),
            "max(<col>)" to arrayOf(ColumnTypeEnum.NUMBER),
            "avg(<col>)" to arrayOf(ColumnTypeEnum.NUMBER),
            "min_by(<col>, lo_quantity)" to arrayOf(ColumnTypeEnum.NUMBER),
            "max_by(<col>, lo_quantity)" to arrayOf(ColumnTypeEnum.NUMBER),
            "stddev(<col>)" to arrayOf(ColumnTypeEnum.NUMBER),
            "percentile_approx(<col>, 0.5)" to arrayOf(ColumnTypeEnum.NUMBER),
            "percentile_cont(<col>, 0.5)" to arrayOf(ColumnTypeEnum.NUMBER),
            "percentile_disc(<col>, 0.5)" to arrayOf(ColumnTypeEnum.NUMBER),

            "count(<col>)" to arrayOf(ColumnTypeEnum.ALL),
            "ndv(<col>)" to arrayOf(ColumnTypeEnum.ALL),
            "approx_count_distinct(<col>)" to arrayOf(ColumnTypeEnum.ALL),
            "array_agg(<col>)" to arrayOf(ColumnTypeEnum.ALL),

            "bitmap_union(to_bitmap(<col>))" to arrayOf(ColumnTypeEnum.NUMBER),
            "bitmap_union(bitmap_hash(<col>))" to arrayOf(ColumnTypeEnum.STRING),
        )
        val joinOps: Array<String> = arrayOf(
            "inner",
            "left outer",
            "right outer",
            "left semi",
            "right semi",
            "left anti",
            "right anti",
            "cross",
            "full outer",
        )
    }
}