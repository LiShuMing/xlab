package com.starrocks.itest.framework.schema

abstract sealed class Field(open val name: String) {
    abstract fun sqlType(): String
    open fun sql(): String = "$name ${sqlType()} NOT NULL"
    fun simple(): SF {
        return when (this) {
            is CF -> {
                this.fld
            }

            is SF -> {
                this
            }

            is AggregateField -> this.fld.simple()
        }
    }

    fun type_id(): String {
        return when (val f = this.simple()) {
            is FixedLengthField -> {
                return f.type.name.removePrefix("TYPE_").toLowerCase()
            }

            is VarCharField -> {
                return "varchar${f.len}"
            }

            is CharField -> {
                return "char${f.len}"
            }

            is DecimalField -> {
                return "decimal${f.bits}p${f.precision}s${f.scale}"
            }

            is DecimalV2Field -> {
                return "decimalv2"
            }

            is BitmapField -> {
                return "bitmap"
            }

            is HllField -> {
                return "hll"
            }

            is JsonField -> {
                return "json"
            }

            is PercentileField -> {
                return "percentile"
            }
        }
    }

    fun rename(name: String): Field {
        return when (this) {
            is SF -> {
                when (this) {
                    is FixedLengthField -> SF.fixedLength(name, this.type)
                    is CharField -> SF.char(name, this.len)
                    is VarCharField -> SF.varchar(name, this.len)
                    is DecimalField -> SF.decimal(name, this.bits, this.precision, this.scale)
                    is DecimalV2Field -> SF.decimalv2(name, this.precision, this.scale)
                    is BitmapField -> TODO()
                    is HllField -> TODO()
                    is JsonField -> TODO()
                    is PercentileField -> TODO()
                }
            }

            is NullableField -> CF.nullable(this.fld.rename(name) as SF, this.nullRatio)
            is TrivialCF -> CF.trivial(this.fld.rename(name) as SF)
            is DefaultValueField -> CF.default_value(this.fld.rename(name) as SF, this.value)
            is NullableDefaultValueField -> CF.nullable_default_value(
                fld.rename(name) as SF,
                this.nullRatio,
                this.value
            )

            is AggregateField -> AggregateField.aggregate(this.fld.rename(name) as CF, this.aggType)
        }
    }
}

abstract sealed class SF(override val name: String) : Field(name) {
    companion object {
        fun fixedLength(name: String, type: FixedLengthType): SF = FixedLengthField(name, type)
        fun tinyint(name: String): SF = FixedLengthField(name, FixedLengthType.TYPE_TINYINT)
        fun boolean(name: String): SF = FixedLengthField(name, FixedLengthType.TYPE_BOOLEAN)
        fun int(name: String): SF = FixedLengthField(name, FixedLengthType.TYPE_INT)
        fun bigint(name: String): SF = FixedLengthField(name, FixedLengthType.TYPE_BIGINT)
        fun double(name: String): SF = FixedLengthField(name, FixedLengthType.TYPE_DOUBLE)
        fun date(name: String): SF = FixedLengthField(name, FixedLengthType.TYPE_DATE)

        fun datetime(name: String): SF = FixedLengthField(name, FixedLengthType.TYPE_DATETIME)
        fun char(name: String, len: Int): SF = CharField(name, len)
        fun varchar(name: String, len: Int): SF = VarCharField(name, len)
        fun decimal(name: String, bits: Int, precision: Int, scale: Int) = DecimalField(name, bits, precision, scale)
        fun decimalv2(name: String, precision: Int, scale: Int) = DecimalV2Field(name, precision, scale)
        fun hll(name: String) = HllField(name)
        fun bitmap(name: String) = BitmapField(name)
        fun percentile(name: String) = PercentileField(name)
        fun json(name: String) = JsonField(name)
    }

    fun precisionAndScale(): Pair<Int, Int> {
        return when (this) {
            is DecimalField -> this.precision to this.scale
            is DecimalV2Field -> this.precision to this.scale
            else -> -1 to -1
        }
    }

    fun primitiveType(): String {
        return when (this) {
            is FixedLengthField -> this.type.toString()
            is DecimalV2Field -> "TYPE_DECIMALV2"
            is DecimalField -> "TYPE_DECIMAL${this.bits}"
            is CharField -> "TYPE_CHAR"
            is VarCharField -> "TYPE_VARCHAR"
            is BitmapField -> "TYPE_BITMAP"
            is HllField -> "TYPE_HLL"
            is JsonField -> "TYPE_JSON"
            is PercentileField -> "TYPE_PERCENTILE"
        }
    }

    fun uniqueType(): String {
        val (p, s) = precisionAndScale()
        val pType = primitiveType().substring("TYPE_".length).toLowerCase().capitalize()
        return when (this) {
            is FixedLengthField -> when (this.type) {
                FixedLengthType.TYPE_TINYINT -> "TinyInt"
                FixedLengthType.TYPE_SMALLINT -> "SmallInt"
                FixedLengthType.TYPE_BIGINT -> "BigInt"
                FixedLengthType.TYPE_LARGEINT -> "LargeInt"
                else -> pType
            }

            is DecimalField -> "${pType}p${p}s${s}"
            else -> pType
        }
    }

    override fun sqlType(): String {
        val typ = this.uniqueType().toUpperCase()
        return when (this) {
            is FixedLengthField -> typ
            is CharField -> "$typ(${this.len})"
            is VarCharField -> "$typ(${this.len})"
            is DecimalField -> "DECIMAL${this.bits}(${this.precision}, ${this.scale})"
            is DecimalV2Field -> "DECIMALV2(${this.precision}, ${this.scale})"
            is BitmapField -> "BITMAP"
            is HllField -> "HLL"
            is JsonField -> "JSON"
            is PercentileField -> "PERCENTILE"
        }
    }

    fun baseType(): String {
        val typ = this.uniqueType().toUpperCase()
        return when (this) {
            is DecimalField -> "DECIMAL${this.bits}(${this.precision}, ${this.scale})"
            is DecimalV2Field -> "DECIMALV2(${this.precision}, ${this.scale})"
            else -> typ
        }
    }

    fun toNumeric(): String {
        return when (this) {
            is CharField, is VarCharField -> "length(${this.name})"
            is DecimalField, is DecimalV2Field -> "${this.name}"
            is FixedLengthField -> when (type) {
                FixedLengthType.TYPE_BOOLEAN -> "if(${this.name}, 1, 0)"
                FixedLengthType.TYPE_DATE, FixedLengthType.TYPE_DATETIME -> "cast(${this.name} as BIGINT)"
                else -> "${this.name}"
            }

            is BitmapField -> "bitmap_count(${this.name})"
            is HllField -> "hll_cardinality(${this.name})"
            is JsonField -> "json_length(${this.name})"
            is PercentileField -> "percentile_approx_raw(${this.name},0.5)"
        }
    }

    fun toHll(): String {
        return when (this) {
            is HllField -> this.name
            is BitmapField, is JsonField, is PercentileField -> "hll_hash(${this.toNumeric()})"
            else -> "hll_hash(${this.name})"
        }
    }

    fun castTo(fd: SF): String {
        return if (fd.primitiveType() == this.primitiveType()) {
            "${this.name}"
        } else {
            when (fd) {
                is BitmapField -> "bitmap_hash(${name})"
                is HllField -> "hll_hash(${name})"
                is PercentileField -> "percentile_hash(${name})"
                else -> "cast(${name} as ${fd.baseType()})"
            }
        }
    }

    fun toBitmap(): String {
        return when (this) {
            is BitmapField -> this.name
            is HllField, is JsonField, is PercentileField -> "bitmap_hash(${this.toNumeric()})"
            else -> "bitmap_hash(${this.name})"
        }
    }

    fun toPercentile(): String {
        return when (this) {
            is PercentileField -> this.name
            is HllField, is JsonField, is BitmapField -> "percentile_hash(${this.toNumeric()})"
            else -> "percentile_hash(${this.name})"
        }
    }

    fun toArraySupportType(): String {
        return when (this) {
            is DecimalField, is DecimalV2Field -> "cast(${this.name} as INT)"
            is HllField, is JsonField, is BitmapField, is PercentileField -> this.toNumeric()
            else -> this.name
        }
    }

    fun toVarchar(): String {
        return when (this) {
            is VarCharField -> this.name
            is CharField -> "cast(${this.name} as VARCHAR)"
            else -> "cast(${this.toNumeric()} as VARCHAR)"
        }
    }

    fun toBigInt(): String {
        return when (this) {
            is FixedLengthField -> "cast(${this.name} as BIGINT)"
            else -> "cast(${this.toNumeric()} as BIGINT)"
        }
    }

    fun toInt(): String {
        return when (this) {
            is FixedLengthField -> "cast(${this.name} as INT)"
            else -> "cast(${this.toNumeric()} as INT)"
        }
    }

    fun toDouble(): String {
        return when (this) {
            is FixedLengthField -> "cast(${this.name} as DOUBLE)"
            else -> "cast(${this.toNumeric()} as DOUBLE)"
        }
    }

    fun toTimestamp(): String {
        val ts = "(seconds_add('2022-01-01 00:00:00', ((${this.toBigInt()}) % 86400)))"
        return when (this) {
            is FixedLengthField -> when (type) {
                FixedLengthType.TYPE_DATE, FixedLengthType.TYPE_DATETIME -> this.name
                else -> ts
            }

            else -> ts
        }
    }

}

abstract sealed class CF(open val fld: SF) : Field(fld.name) {
    companion object {
        fun trivial(fld: SF): CF = TrivialCF(fld)
        fun nullable(fld: SF, nullRatio: Int): CF = NullableField(fld, nullRatio)
        fun default_value(fld: SF, value: String): CF = DefaultValueField(fld, value)
        fun nullable_default_value(fld: SF, nullRatio: Int, value: String): CF =
            NullableDefaultValueField(fld, nullRatio, value)
    }

    override fun sqlType(): String = fld.sqlType()

    override fun sql(): String {
        val colDef = this.fld.sql().replace(Regex("NOT\\s+NULL"), "")
        return when (this) {
            is TrivialCF -> fld.sql()
            is NullableField -> "$colDef NULL"
            is DefaultValueField -> "${this.fld.sql()} DEFAULT \"${this.value}\""
            is NullableDefaultValueField -> "$colDef NULL DEFAULT \"${this.value}\""
        }
    }
}

enum class FixedLengthType {
    TYPE_BOOLEAN,
    TYPE_TINYINT,
    TYPE_SMALLINT,
    TYPE_INT,
    TYPE_BIGINT,
    TYPE_LARGEINT,
    TYPE_FLOAT,
    TYPE_DOUBLE,
    TYPE_DATE,
    TYPE_DATETIME,
}

enum class AggregateType {
    NONE,
    MIN,
    SUM,
    MAX,
    HLL_UNION,
    BITMAP_UNION,
    REPLACE,
    REPLACE_IF_NOT_NULL,
    UNKNOWN,
    PERCENTILE_UNION,
}

data class FixedLengthField(override val name: String, val type: FixedLengthType) : SF(name) {}
data class CharField(override val name: String, val len: Int) : SF(name) {}
data class VarCharField(override val name: String, val len: Int) : SF(name) {}
data class DecimalField(override val name: String, val bits: Int, val precision: Int, val scale: Int) :
    SF(name) {}

data class DecimalV2Field(override val name: String, val precision: Int, val scale: Int) : SF(name) {}
data class NullableField(override val fld: SF, val nullRatio: Int) : CF(fld) {}
data class TrivialCF(override val fld: SF) : CF(fld) {}
data class DefaultValueField(override val fld: SF, val value: String) : CF(fld) {}
data class NullableDefaultValueField(override val fld: SF, val nullRatio: Int, val value: String) :
    CF(fld) {}

data class AggregateField(val fld: CF, val aggType: AggregateType) : Field(fld.name) {
    companion object {
        private fun rectifyAggType(f: SF, aggType: AggregateType): AggregateType {
            return when (f) {
                is BitmapField -> AggregateType.BITMAP_UNION
                is HllField -> AggregateType.HLL_UNION
                is PercentileField -> AggregateType.PERCENTILE_UNION
                else -> aggType
            }
        }

        fun aggregate(fld: CF, aggType: AggregateType) = AggregateField(fld, rectifyAggType(fld.simple(), aggType))
    }

    override fun sqlType(): kotlin.String {
        return when (aggType) {
            AggregateType.NONE -> fld.sqlType()
            else -> fld.sqlType() + " " + aggType.name
        }
    }

    override fun sql(): String {
        if (aggType == AggregateType.NONE) {
            return this.fld.sql()
        }

        val colDef = this.fld.fld.sql().replace(Regex("NOT\\s+NULL"), "")
        return when (this.fld) {
            is TrivialCF -> "$colDef ${aggType.name} NOT NULL"
            is NullableField -> "$colDef ${aggType.name} NULL"
            is DefaultValueField -> "$colDef ${aggType.name} DEFAULT \"${this.fld.value}\""
            is NullableDefaultValueField -> "$colDef ${aggType.name} NULL DEFAULT \"${this.fld.value}\""
        }
    }
}

data class HllField(override val name: String) : SF(name) {}
data class BitmapField(override val name: String) : SF(name) {}
data class PercentileField(override val name: String) : SF(name) {}
data class JsonField(override val name: String) : SF(name) {}

fun allFields(): Array<Field> {
    return arrayOf(
        SF.fixedLength("", FixedLengthType.TYPE_BOOLEAN),
        SF.fixedLength("", FixedLengthType.TYPE_INT),
        SF.fixedLength("", FixedLengthType.TYPE_TINYINT),
        SF.fixedLength("", FixedLengthType.TYPE_SMALLINT),
        SF.fixedLength("", FixedLengthType.TYPE_INT),
        SF.fixedLength("", FixedLengthType.TYPE_BIGINT),
        SF.fixedLength("", FixedLengthType.TYPE_LARGEINT),
        SF.fixedLength("", FixedLengthType.TYPE_DATE),
        SF.fixedLength("", FixedLengthType.TYPE_DATETIME),
        SF.fixedLength("", FixedLengthType.TYPE_FLOAT),
        SF.fixedLength("", FixedLengthType.TYPE_DOUBLE),
        SF.varchar("", 64),
        SF.char("", 64),
        SF.decimal("", 32, 7, 4),
        SF.decimal("", 64, 15, 6),
        SF.decimal("", 128, 37, 9)
    )
}

fun createFieldGenerator(): () -> Field {
    var fieldOrdinal = 0
    val allFields = allFields()
    return fun(): Field {
        fieldOrdinal = kotlin.math.abs(fieldOrdinal + 1)
        val f = allFields[fieldOrdinal % allFields.size]
        val label = "000$fieldOrdinal".takeLast(4)
        val fName = "c${label}_${f.type_id()}"
        return f.rename(fName)
    }
}

fun generateFields(n: Int): List<Field> {
    val gen = createFieldGenerator()
    return (1..n).map { gen() }
}

fun generateRandomFields(n: Int): List<Field> {
    val fields = generateFields(n)
    return fields.mapIndexed { i, f ->
        val label = "0000$i".takeLast(4)
        f.rename("c${label}_${f.type_id()}")
    }
}
