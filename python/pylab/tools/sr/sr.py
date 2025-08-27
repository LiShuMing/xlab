sqls = """
select count(*) from t1 where last_day(dt) = '2025-01-01';
SELECT count(*) FROM t1 WHERE last_day(dt) = '2025-01-31';
SELECT count(*) FROM t1 WHERE last_day(dt) = '2025-02-28';
SELECT count(*) FROM t1 WHERE last_day(dt) = '2025-03-31';
SELECT count(*) FROM t1 WHERE last_day(dt) = '2025-04-30';
SELECT count(*) FROM t1 WHERE last_day(dt) = '2025-05-31';
SELECT count(*) FROM t1 WHERE last_day(dt) = '2025-06-30';
SELECT count(*) FROM t1 WHERE last_day(dt) = '2025-07-31';
SELECT count(*) FROM t1 WHERE last_day(dt) = '2025-08-31';
SELECT count(*) FROM t1 WHERE last_day(dt) = '2025-09-30';
SELECT count(*) FROM t1 WHERE last_day(dt) = '2025-10-31';
SELECT count(*) FROM t1 WHERE last_day(dt) = '2025-11-30';
SELECT count(*) FROM t1 WHERE last_day(dt) = '2025-12-31';
SELECT count(*) FROM t1 WHERE last_day(dt) is NULL;
SELECT count(*) FROM t1 WHERE last_day(dt) BETWEEN '2025-01-01' AND '2025-01-31';
SELECT count(*) FROM t1 WHERE last_day(dt) BETWEEN '2025-01-01' AND '2025-02-28';
SELECT count(*) FROM t1 WHERE last_day(dt) BETWEEN '2025-01-01' AND '2025-09-28';
SELECT count(*) FROM t1 WHERE last_day(dt) BETWEEN '2025-01-01' AND '2025-12-28';
SELECT count(*) FROM t1 WHERE last_day(dt) BETWEEN '2025-01-01' AND '2025-12-31';
SELECT count(*) FROM t1 WHERE last_day(dt) BETWEEN '2025-01-01' AND '2025-12-31' or last_day(dt) is NULL;
SELECT count(*) FROM t1 WHERE last_day(dt) = date_trunc('day', dt);
SELECT count(*) FROM t1 WHERE last_day(dt) = date_trunc('month', dt);
SELECT count(*) FROM t1 WHERE last_day(dt) = date_trunc('year', dt);
SELECT count(*) FROM t1 WHERE  date_trunc('day', dt) < '2025-05-30' - INTERVAL 2 MONTH AND last_day(date_trunc('day', dt)) != date_trunc('day', dt);
SELECT count(*) FROM t1 WHERE  date_trunc('day', dt) < '2025-12-30' - INTERVAL 2 MONTH AND last_day(date_trunc('day', dt)) != date_trunc('day', dt);
"""
def func1():
    for sql in sqls.split("\n"):
        if sql.strip() == "":
            continue
        # print("function: check_hit_materialized_view(\"" + sql + "\", \"mv0\", \"UNION\")")
        # print("function: print_hit_materialized_view(\"" + sql + "\", \"test_mv1\")")
        # print("function: print_hit_materialized_views(\"" + sql + "\")")
        # print("function: check_no_hit_materialized_view(\"" + sql + "\", \"test_mv1\")")
        #print(sql[:-1] + " order by dt;")
        print("function: print_plan_partition_selected_num(\"" + sql + "\", \"t1\")")

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
