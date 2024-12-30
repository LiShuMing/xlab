# 计数排序，用于对特定的位进行排序
def counting_sort(arr, exp):
    n = len(arr)
    output = [0] * n  # 存放排序后的结果
    count = [0] * 10  # 计数数组，记录每个数字出现的次数（0-9）
    
    # 计算每个数字在当前位上的出现频率
    for i in range(n):
        index = arr[i] // exp
        count[index % 10] += 1
    
    # 修改 count 数组，使其包含每个数字的最终位置
    for i in range(1, 10):
        count[i] += count[i - 1]
    
    # 根据 count 数组的结果，构造排序后的数组
    for i in range(n - 1, -1, -1):
        index = arr[i] // exp
        output[count[index % 10] - 1] = arr[i]
        count[index % 10] -= 1
    
    # 将排序后的数组复制到原数组中
    for i in range(n):
        arr[i] = output[i]

# Radix Sort 实现
def radix_sort(arr):
    # 找到数组中的最大值
    max_val = max(arr)
    
    # 对每个位进行排序
    exp = 1  # 初始处理最低有效位
    while max_val // exp > 0:
        counting_sort(arr, exp)  # 根据当前位进行计数排序
        exp *= 10  # 处理下一位（十倍扩展）

def test_radix_sort():
    # 测试 Radix Sort
    arr = [170, 45, 75, 90, 802, 24, 2, 66]
    print("Original array:", arr)

    radix_sort(arr)

    print("Sorted array:", arr)