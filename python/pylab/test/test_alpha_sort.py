# AlphaSort 算法的简化实现
def alphasort(arr):
    # 如果只有一个元素，已经排序好了
    if len(arr) <= 1:
        return arr

    # 基于第一个字符进行分割
    pivot = arr[0][0]  # 假设按首字母排序
    left = [x for x in arr if x[0] < pivot]
    right = [x for x in arr if x[0] > pivot]
    middle = [x for x in arr if x[0] == pivot]

    # 对左右子集进行递归排序，并合并结果
    return alphasort(left) + middle + alphasort(right)

def test_alpha_sort():
    arr = ["banana", "apple", "grape", "orange", "kiwi"]
    sorted_arr = alphasort(arr)
    print("Sorted array:", sorted_arr)