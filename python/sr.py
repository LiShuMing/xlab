sqls = """
SELECT distinct prcdate FROM mv_iceberg_${uuid0}.sql_test_db.test_iceberg_with_month order by prcdate;
SELECT distinct prcdate FROM mv_iceberg_${uuid0}.sql_test_db.test_iceberg_with_month where prcdate < '2025-01-03' order by prcdate;
SELECT distinct prcdate FROM mv_iceberg_${uuid0}.sql_test_db.test_iceberg_with_month where prcdate > '2025-01-03' order by prcdate;
"""

values = """(1,"2020-06-15"),(2,"2020-06-18"),(3,"2020-06-21"),(4,"2020-06-24"),
  (1,"2020-07-02"),(2,"2020-07-05"),(3,"2020-07-08"),(4,"2020-07-11"),
  (1,"2020-07-16"),(2,"2020-07-19"),(3,"2020-07-22"),(4,"2020-07-25"),
  (2,"2020-06-15"),(3,"2020-06-18"),(4,"2020-06-21"),(5,"2020-06-24"),
  (2,"2020-07-02"),(3,"2020-07-05"),(4,"2020-07-08"),(5,"2020-07-11");
"""
def func1():
    for sql in sqls.split("\n"):
        if sql.strip() == "":
            continue
        # print("function: check_hit_materialized_view(\"" + sql + "\", \"mv0\", \"UNION\")")
        print("function: print_hit_materialized_view(\"" + sql + "\", \"test_mv1\")")
        # print("function: print_hit_materialized_views(\"" + sql + "\")")
        # print("function: check_no_hit_materialized_view(\"" + sql + "\", \"test_mv1\")")
        #print(sql[:-1] + " order by dt;")

def func2():
    for v in values.split("\n"):
        for vv in v.split("),()"):
            # print(vv)

            dates = []
            for vvv in vv.split(","):
                if "-" not in vvv:
                    continue
                d = vvv.split("\"")[1]
                dates.append(d)
            dup_dates = list(set([x for x in dates if dates.count(x) == 1]))
            dup_dates.sort()
            for d in dup_dates:
                # print(d)
                #part = "PARTITION p%s VALUES [(\"%s 00:00:00\"), (\"%s 00:00:00\"))," % (d.replace("-", ""), d, d)
                part = "PARTITION p%s VALUES LESS THAN (\"%s\")," % (int(d.replace("-", "")) - 1, d)
                print(part)
if __name__ == '__main__':
    func1()
