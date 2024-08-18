import sqlparse

from sqlparse.sql import Identifier
from sqlparse.sql import Comparison
from sqlparse import tokens as T
import os
import sys
sys.path.append("../")
from lib.utils import *

class HandleSQL(object):
    def __init__(self) -> None:
        pass

    def handle_file(self, fn):
        content = get_content(fn)
        print(content)
        parsed = sqlparse.parse(content)[0]
        print(parsed)
        print(parsed.tokens)

        table_names = []
        join_conjs = []
        table_name_maps = {}

        for token in parsed.tokens:
            if isinstance(token, Identifier):
                table_names.append(token.get_real_name())
                table_name_maps[token.get_alias()] = token.get_real_name()
                print(token)
            if isinstance(token, Comparison):
                conj = token.value
                print("CONJ:" + conj)
                for i in conj.split("="):
                    join_conjs.append(i)
        print(set(table_names))
        print(join_conjs)
        print(table_name_maps)
        table_join_cols = {}
        for conj in join_conjs:
            arr = conj.split(".")
            print(arr)
            tbl_name = arr[0][1:-1]
            col = arr[1]
            real_tbl_name = table_name_maps[tbl_name]
            if real_tbl_name not in table_join_cols:
                table_join_cols[real_tbl_name] = []
            table_join_cols[real_tbl_name].append(col[1:-1])
        for k,v in table_join_cols.items():
            table_join_cols[k] = set(v)
        print(table_join_cols)

    def convert_hive_to_sr(self, fn):
        print("start to handle: ", fn)
        content = get_content(fn)
        # print(content)
        parsed = sqlparse.parse(content)[0]
        # print(parsed.tokens)

        create_table = None
        partition_by = ""
        is_partition_by = False
        for token in parsed.tokens:
            if isinstance(token, Identifier) and create_table is None:
                create_table = str(token)
            elif token.ttype == T.Keyword and token.value == "BY":
                print("it's partition by")
                is_partition_by = True
            else:
                if is_partition_by and token.ttype != T.Text.Whitespace:
                    partition_by = str(token.value)
                    is_partition_by = False

        create_columns = create_table.split("PARTITION")[0]
        table_name = create_columns.split("(")[0]
        print(table_name)

        sr_ddl = "CREATE TABLE " + create_columns + """
         ENGINE=OLAP
DUPLICATE KEY(`c_custkey`)
DISTRIBUTED BY HASH(`c_custkey`) BUCKETS 10
PARTITION BY (dt)
PROPERTIES (
"replication_num" = "1",
"in_memory" = "false",
"storage_format" = "DEFAULT"
)"""
        return table_name, sr_ddl

if __name__ == "__main__":
    h1 = HandleSQL()
    # h1.handle_file("/Users/lishuming/Downloads/pingan/create_mv1.sql")
    ddl_dir = "/Users/lishuming/Downloads/pingan/ddl"
    ddls = os.listdir(ddl_dir)
    for ddl in ddls:

        print(ddl)
        real_path = os.path.join(ddl_dir, ddl)
        if real_path.endswith("/sr"):
            continue
        if "stat_rpsm.md_d_pw_prod_fund_buy_order_stat.sql" not in real_path:
            continue
        tbl_name, sr_ddl = h1.convert_hive_to_sr(real_path)
        print(sr_ddl.strip())
        output_file_name = os.path.join(ddl_dir, "sr", tbl_name.strip()[1:-1] + ".sql")
        write_content(output_file_name, sr_ddl)
