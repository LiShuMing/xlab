import pytest
from datetime import datetime, timedelta
import random


def test_sort_1():
    print("start test_sort_1")
    datas = []
    for i in range(1, 100):
        data = {"key":1, "c0":i}
        datas.append(data)
    print(datas)
    new_list = sorted(datas, key = lambda x: x["c0"], reverse = False)
    print(new_list)

    for i in (0, 1, 100, -1):
        for j in (0, 10):
            print("-----------j:%s i:%s--------" % (j, i))
            print(datas[j:i])

def quicksort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quicksort(left) + middle + quicksort(right)

def test_sort_2():
    print("start test_sort_2")
    print(quicksort([3,6,8,10,1,2,1]))

def print1():
    t1 = """
    @Ignore
    @Test
    public void testQuery<SEQ>() {
        runFileUnitTest("materialized-view/tpch/q<SEQ>");
    }
    """
    for i in range (1, 23):
        tt = t1.replace("<SEQ>", str(i))
        print(tt)

def handle_files(f_name):
    fp = open(f_name)
    content = ""
    flag = True
    for line in fp.readlines():
        if "[result]" in line:
            content += line
            flag = False
            continue
        if "[end]" in line:
            flag = True
        if not flag:
            continue
        content += line
    print(content)
    fp.close()
    fp2 = open(f_name, 'w')
    fp2.write(content)
    fp2.close()

@pytest.mark.skip(reason="Not implemented yet")
def test_handle_files():
    # test_sort_1()
    # print1()
    f_dir = "/Users/lishuming/work/starrocks/fe/fe-core/src/test/resources/sql/materialized-view/tpch"
    for i in range(1, 23):
        f_name = f_dir + "/q" + str(i) + ".sql"
        handle_files(f_name)

def generate_data():
    data = []
    start_date = datetime(2023, 1, 1)  # 数据起始日期
    end_date = datetime(2023, 12, 31)  # 数据结束日期

    for i in range(1, 10):  # 生成10万条数据
        ship_date = start_date + timedelta(days=random.randint(0, 364))
        commit_date = ship_date + timedelta(days=random.randint(1, 10))
        receipt_date = commit_date + timedelta(days=random.randint(1, 5))
        data.append((
            random.randint(1, 1000000),   # l_orderkey
            random.randint(1, 100000),    # l_partkey
            random.randint(1, 50000),     # l_suppkey
            random.randint(1, 10),        # l_linenumber
            str(round(random.uniform(1, 100), 2)),  # l_quantity
            str(round(random.uniform(10, 1000), 2)),  # l_extendedprice
            str(round(random.uniform(0, 0.1), 2)),   # l_discount
            str(round(random.uniform(0, 0.2), 2)),   # l_tax
            random.choice(['A', 'B', 'C']),     # l_returnflag
            random.choice(['O', 'F']),          # l_linestatus
            ship_date,                          # l_shipdate
            commit_date,                        # l_commitdate
            receipt_date,                       # l_receiptdate
            random.choice(['DELIVER IN PERSON', 'COLLECT FROM STORE']),  # l_shipinstruct
            random.choice(['AIR', 'RAIL', 'TRUCK']),                    # l_shipmode
            "Generated comment {}".format(i)    # l_comment
        ))
    return data

def test_generate_data():
    data = generate_data()
    print(data)