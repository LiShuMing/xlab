import pytest

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
