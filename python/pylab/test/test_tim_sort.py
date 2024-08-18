# 插入排序实现
def insertion_sort(arr, left, right):
    for i in range(left + 1, right + 1):
        key = arr[i]
        j = i - 1
        while j >= left and arr[j] > key:
            arr[j + 1] = arr[j]
            j -= 1
        arr[j + 1] = key

# 合并两个有序数组的实现
def merge(arr, left, mid, right):
    # 获取两个子数组
    left_subarray = arr[left:mid + 1]
    right_subarray = arr[mid + 1:right + 1]
    
    # 合并两个子数组
    i = 0  # 左子数组的索引
    j = 0  # 右子数组的索引
    k = left  # 合并后的数组的索引
    
    while i < len(left_subarray) and j < len(right_subarray):
        if left_subarray[i] <= right_subarray[j]:
            arr[k] = left_subarray[i]
            i += 1
        else:
            arr[k] = right_subarray[j]
            j += 1
        k += 1
    
    # 处理左子数组的剩余元素
    while i < len(left_subarray):
        arr[k] = left_subarray[i]
        i += 1
        k += 1
    
    # 处理右子数组的剩余元素
    while j < len(right_subarray):
        arr[k] = right_subarray[j]
        j += 1
        k += 1

# TimSort的实现
def tim_sort(arr):
    # 设定run的大小
    RUN = 32
    n = len(arr)
    
    # 对数组分成小的子数组，并用插入排序进行排序
    for start in range(0, n, RUN):
        end = min(start + RUN - 1, n - 1)
        insertion_sort(arr, start, end)
    
    # 合并这些小的有序子数组
    size = RUN
    while size < n:
        for start in range(0, n, size * 2):
            mid = min(n - 1, start + size - 1)
            end = min((start + size * 2 - 1), (n - 1))
            if mid < end:
                merge(arr, start, mid, end)
        size *= 2
    
    return arr

def test_tim_sort():
    # 测试
    arr = [5, 21, 7, 23, 19, 3, 18, 22, 9, 12]
    sorted_arr = tim_sort(arr)
    print("Sorted Array:", sorted_arr)