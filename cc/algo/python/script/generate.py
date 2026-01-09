import re

DDL = r"""


CREATE TABLE db_mock_000.tbl_mock_205 (
mock_249 largeint(40) NOT NULL ,
id varchar(65535) ,
mock_176 datetime ,
mock_175 varchar(65535) ,
mock_193 varchar(65535) ,
mock_264 varchar(65535) ,
mock_265 varchar(65535) ,
mock_250 varchar(65535) ,
mock_251 varchar(65535) ,
mock_261 varchar(65535) ,
mock_260 varchar(65535) ,
mock_270 varchar(65535) ,
mock_271 varchar(65535) ,
mock_259 varchar(65535) ,
mock_262 varchar(65535) ,
mock_268 varchar(65535) ,
mock_269 varchar(65535) ,
mock_253 varchar(65535) ,
mock_254 varchar(65535) ,
mock_266 varchar(65535) ,
mock_267 varchar(65535) ,
mock_190 double ,
mock_177 varchar(65535) ,
mock_255 varchar(65535) ,
mock_256 varchar(65535) ,
mock_202 varchar(65535) ,
mock_182 varchar(65535) ,
mock_263 datetime ,
mock_073 varchar(65535) ,
mock_072 varchar(65535) ,
mock_258 varchar(65535) ,
mock_257 datetime ,
mock_174 varchar(65535) ,
mock_252 varchar(65535) ,
mock_242 largeint(40) ,
mock_240 largeint(40) ,
mock_247 largeint(40) ,
mock_245 largeint(40) ,
mock_244 largeint(40) ,
mock_243 largeint(40) ,
mock_246 largeint(40) ,
mock_248 largeint(40) ,
mock_238 largeint(40) ,
mock_237 largeint(40) ,
mock_241 largeint(40) ,
mock_239 largeint(40) ,
mock_154 largeint(40) ,
mock_059 largeint(40) ,
mock_236 largeint(40) ,
mock_037 datetime ,
mock_038 datetime ,
mock_040 datetime ,
mock_041 datetime ,
mock_042 datetime ,
mock_043 datetime ,
mock_044 datetime ,
mock_045 datetime ,
mock_046 datetime ,
mock_047 datetime ,
mock_039 datetime ,
mock_048 varchar(65533) ,
mock_049 varchar(65533) ,
mock_051 varchar(65533) ,
mock_052 varchar(65533) ,
mock_053 varchar(65533) ,
mock_054 varchar(65533) ,
mock_055 varchar(65533) ,
mock_056 varchar(65533) ,
mock_057 varchar(65533) ,
mock_058 varchar(65533) ,
mock_050 varchar(65533) ,
mock_098 bigint(20) ,
mock_099 bigint(20) ,
mock_110 bigint(20) ,
mock_113 bigint(20) ,
mock_114 bigint(20) ,
mock_115 bigint(20) ,
mock_116 bigint(20) ,
mock_117 bigint(20) ,
mock_118 bigint(20) ,
mock_119 bigint(20) ,
mock_100 bigint(20) ,
mock_101 bigint(20) ,
mock_102 bigint(20) ,
mock_103 bigint(20) ,
mock_104 bigint(20) ,
mock_105 bigint(20) ,
mock_106 bigint(20) ,
mock_107 bigint(20) ,
mock_108 bigint(20) ,
mock_109 bigint(20) ,
mock_111 bigint(20) ,
mock_112 bigint(20) ,
mock_206 bigint(20) ,
mock_207 bigint(20) ,
mock_208 bigint(20) ,
mock_209 bigint(20) ,
mock_210 bigint(20) ,
mock_211 bigint(20) ,
mock_212 bigint(20) ,
mock_213 bigint(20) ,
mock_214 bigint(20) ,
mock_215 bigint(20) ,
mock_216 bigint(20) ,
mock_217 bigint(20) ,
mock_218 bigint(20) ,
mock_219 bigint(20) ,
mock_220 bigint(20) ,
mock_221 bigint(20) ,
mock_222 bigint(20) ,
mock_223 bigint(20) ,
mock_224 bigint(20) ,
mock_225 bigint(20) ,
mock_226 bigint(20) ,
mock_227 bigint(20) ,
mock_228 bigint(20) ,
mock_229 bigint(20) ,
mock_230 bigint(20) ,
mock_231 bigint(20) ,
mock_232 bigint(20) ,
mock_233 bigint(20) ,
mock_234 bigint(20) ,
mock_235 bigint(20) ,
mock_141 double ,
mock_142 double ,
mock_144 double ,
mock_145 double ,
mock_146 double ,
mock_147 double ,
mock_148 double ,
mock_149 double ,
mock_150 double ,
mock_151 double ,
mock_143 double ,
mock_004 array<datetime> ,
mock_005 array<datetime> ,
mock_007 array<datetime> ,
mock_008 array<datetime> ,
mock_009 array<datetime> ,
mock_010 array<datetime> ,
mock_011 array<datetime> ,
mock_012 array<datetime> ,
mock_013 array<datetime> ,
mock_014 array<datetime> ,
mock_006 array<datetime> ,
mock_015 array<largeint(40)> ,
mock_016 array<largeint(40)> ,
mock_018 array<largeint(40)> ,
mock_019 array<largeint(40)> ,
mock_020 array<largeint(40)> ,
mock_021 array<largeint(40)> ,
mock_022 array<largeint(40)> ,
mock_023 array<largeint(40)> ,
mock_024 array<largeint(40)> ,
mock_025 array<largeint(40)> ,
mock_017 array<largeint(40)> ,
mock_026 array<varchar(65533)> ,
mock_027 array<varchar(65533)> ,
mock_029 array<varchar(65533)> ,
mock_030 array<varchar(65533)> ,
mock_031 array<varchar(65533)> ,
mock_032 array<varchar(65533)> ,
mock_033 array<varchar(65533)> ,
mock_034 array<varchar(65533)> ,
mock_035 array<varchar(65533)> ,
mock_036 array<varchar(65533)> ,
mock_028 array<varchar(65533)> 
) ENGINE= OLAP 
PRIMARY KEY(mock_249)
DISTRIBUTED BY HASH(mock_249) BUCKETS 20 
PROPERTIES (
"replication_num" = "1"
);
"""

def parse_columns(ddl: str):
    # Grab content between first '(' after table name and the matching ') ENGINE'
    m = re.search(r"\(\s*(.*)\)\s*ENGINE\s*=", ddl, re.S | re.I)
    if not m:
        raise ValueError("Cannot find column definition block '(...) ENGINE=' in DDL.")
    body = m.group(1)

    cols = []
    depth = 0
    token = []
    for ch in body:
        if ch == '<':
            depth += 1
        elif ch == '>':
            depth -= 1
        if ch == ',' and depth == 0:
            item = ''.join(token).strip()
            token = []
            if item:
                cols.append(item)
        else:
            token.append(ch)
    last = ''.join(token).strip()
    if last:
        cols.append(last)

    # Extract column name: first identifier in each column line
    names = []
    for line in cols:
        line = line.strip()
        if not line or line.upper().startswith(("PRIMARY KEY", "KEY", "INDEX")):
            continue
        # column name is first token before whitespace
        name = line.split()[0].strip('`')
        names.append(name)
    return names

def mock_value(coldef: str):
    # crude type-based mock; safe defaults
    coldef_l = coldef.lower()
    if "array<" in coldef_l:
        inner = re.search(r"array<\s*([^>]+)\s*>", coldef_l)
        inner_t = inner.group(1).strip() if inner else ""
        if "datetime" in inner_t:
            return "['2024-01-01 00:00:00']"
        if "int" in inner_t or "bigint" in inner_t or "largeint" in inner_t:
            return "[1]"
        return "['a']"
    if "datetime" in coldef_l:
        return "'2024-01-01 00:00:00'"
    if "double" in coldef_l or "float" in coldef_l:
        return "1.0"
    if "largeint" in coldef_l or "bigint" in coldef_l or "int" in coldef_l:
        return "1"
    if "varchar" in coldef_l or "char" in coldef_l or "string" in coldef_l:
        return "'v'"
    return "NULL"

def extract_table_name(ddl: str) -> str:
    """Extract table name from CREATE TABLE statement in DDL."""
    match = re.search(r"CREATE\s+TABLE\s+([^\s(]+)", ddl, re.I)
    if match:
        return match.group(1)
    raise ValueError("Cannot find table name in DDL")


def build_insert(ddl: str, dbtbl: str):
    # same splitting logic to keep coldefs for type info
    m = re.search(r"\(\s*(.*)\)\s*ENGINE\s*=", ddl, re.S | re.I)
    body = m.group(1)

    items = []
    depth = 0
    token = []
    for ch in body:
        if ch == '<':
            depth += 1
        elif ch == '>':
            depth -= 1
        if ch == ',' and depth == 0:
            item = ''.join(token).strip()
            token = []
            if item:
                items.append(item)
        else:
            token.append(ch)
    last = ''.join(token).strip()
    if last:
        items.append(last)

    coldefs = []
    for line in items:
        line = line.strip()
        if not line or line.upper().startswith(("PRIMARY KEY", "KEY", "INDEX")):
            continue
        coldefs.append(line)

    colnames = [cd.split()[0].strip('`') for cd in coldefs]
    values = [mock_value(cd) for cd in coldefs]

    sql = (
        f"INSERT INTO {dbtbl} (\n  " +
        ",\n  ".join(colnames) +
        "\n) VALUES (\n  " +
        ",\n  ".join(values) +
        "\n);"
    )
    return sql, len(colnames), len(values)

dbtbl = extract_table_name(DDL)
sql, ncols, nvals = build_insert(DDL, dbtbl)
print("columns:", ncols, "values:", nvals)
print(sql)