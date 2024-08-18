from decimal import Decimal
import random
# 假设我们已经实现了 Radix Join 相关的函数
# 包括 radix_join, radix_sort, stable_sort_by_digit, bucketize 等

def radix_join(R1, R2, key):
    result = []
    
    # 1. 对 R1 和 R2 按连接键的最低位进行排序
    R1_sorted = radix_sort(R1, key)
    R2_sorted = radix_sort(R2, key)
    
    # 2. 对 R1 和 R2 执行分桶和连接
    R1_buckets = bucketize(R1_sorted, key)
    R2_buckets = bucketize(R2_sorted, key)
    
    # 3. 遍历每个桶进行局部连接
    for bucket in R1_buckets:
        if bucket in R2_buckets:
            print(bucket)
            # 在相同的桶内执行连接操作
            for tuple1 in R1_buckets[bucket]:
                for tuple2 in R2_buckets[bucket]:
                    if tuple1[key] == tuple2[key]:  # 如果连接键匹配
                        result.append(tuple1 + tuple2)  # 合并元组
    
    # 4. 递归地对更高位进行排序，逐步减少连接操作范围
    return result

def radix_sort(data, key):
    max_key_value = max([tuple[key] for tuple in data])
    max_digit = len(str(max_key_value))  # 根据连接键的最大值来确定位数
    
    for digit in range(max_digit):
        data = stable_sort_by_digit(data, key, digit)
    
    return data

def stable_sort_by_digit(data, key, digit):
    return sorted(data, key=lambda x: get_digit(x[key], digit))

def get_digit(number, digit):
    return (number // 10**digit) % 10

def bucketize(data, key):
    buckets = {}
    for tuple in data:
        bucket_key = tuple[key]
        if bucket_key not in buckets:
            buckets[bucket_key] = []
        buckets[bucket_key].append(tuple)
    return buckets

# --- 测试代码 ---
def test_radix_join():
    # 示例数据集，键是数字
    R1 = [(1, 'a'), (2, 'b'), (3, 'c'), (4, 'd')]
    R2 = [(1, 'apple'), (2, 'banana'), (4, 'date'), (5, 'elderberry')]

    # 执行 Radix Join，连接键是数字（第一个字段）
    result = radix_join(R1, R2, 0)
    
    # 打印结果
    print("Join result:")
    for r in result:
        print(r)

    # 期望输出：(1, 'a', 1, 'apple')
    #            (2, 'b', 2, 'banana')
    #            (4, 'd', 4, 'date')
    