def bitonic_sort(arr, ascending=True):
    if len(arr) <= 1:
        return arr
    mid = len(arr) // 2
    first_half = bitonic_sort(arr[:mid], True)
    second_half = bitonic_sort(arr[mid:], False)
    return bitonic_merge(first_half + second_half, ascending)

def bitonic_merge(arr, ascending):
    if len(arr) == 1:
        return arr
    mid = len(arr) // 2
    for i in range(mid):
        if (arr[i] > arr[i + mid]) == ascending:
            arr[i], arr[i + mid] = arr[i + mid], arr[i]
    first_half = bitonic_merge(arr[:mid], ascending)
    second_half = bitonic_merge(arr[mid:], ascending)
    return first_half + second_half