//! Efficient O(n log n) sorting algorithms
//!
//! These algorithms provide good performance for large datasets
//! and have guaranteed or average O(n log n) time complexity.

use std::cmp::Reverse;
use std::collections::BinaryHeap;

/// Merge Sort
///
/// Divide-and-conquer algorithm that divides the array into halves,
/// recursively sorts them, and then merges the sorted halves.
///
/// # Performance
///
/// - Best/Average/Worst: O(n log n)
/// - Space: O(n) - requires auxiliary array
/// - Stable: Yes
///
/// # Examples
///
/// ```
/// use rlab::common::sort::merge_sort;
///
/// let mut arr = [38, 27, 43, 3, 9, 82, 10];
/// merge_sort(&mut arr);
/// assert_eq!(arr, [3, 9, 10, 27, 38, 43, 82]);
/// ```
pub fn merge_sort<T: Ord + Clone>(arr: &mut [T]) {
    let n = arr.len();
    if n <= 1 {
        return;
    }

    // Allocate temporary array once
    let mut temp = arr.to_vec();
    merge_sort_helper(arr, &mut temp, 0, n);
}

fn merge_sort_helper<T: Ord + Clone>(arr: &mut [T], temp: &mut [T], left: usize, right: usize) {
    if right - left <= 1 {
        return;
    }

    let mid = left + (right - left) / 2;

    // Sort both halves
    merge_sort_helper(arr, temp, left, mid);
    merge_sort_helper(arr, temp, mid, right);

    // Merge into temporary array
    let (mut i, mut j, mut k) = (left, mid, left);

    while i < mid && j < right {
        if arr[i] <= arr[j] {
            temp[k] = arr[i].clone();
            i += 1;
        } else {
            temp[k] = arr[j].clone();
            j += 1;
        }
        k += 1;
    }

    while i < mid {
        temp[k] = arr[i].clone();
        i += 1;
        k += 1;
    }

    while j < right {
        temp[k] = arr[j].clone();
        j += 1;
        k += 1;
    }

    // Copy back to original array
    arr[left..right].clone_from_slice(&temp[left..right]);
}

/// In-place Merge Sort (iterative, bottom-up)
///
/// Non-recursive merge sort that sorts subarrays of size 1, 2, 4, 8, ...
/// Requires O(n) auxiliary space but has better cache performance.
pub fn merge_sort_bottom_up<T: Ord + Clone>(arr: &mut [T]) {
    let n = arr.len();
    if n <= 1 {
        return;
    }

    let mut temp = arr.to_vec();
    let mut width = 1;

    while width < n {
        for left in (0..n).step_by(2 * width) {
            let mid = (left + width).min(n);
            let right = (left + 2 * width).min(n);

            merge_slices(&arr[left..mid], &arr[mid..right], &mut temp[left..right]);
            arr[left..right].clone_from_slice(&temp[left..right]);
        }
        width *= 2;
    }
}

fn merge_slices<T: Ord + Clone>(left: &[T], right: &[T], dest: &mut [T]) {
    let (mut i, mut j, mut k) = (0, 0, 0);

    while i < left.len() && j < right.len() {
        if left[i] <= right[j] {
            dest[k] = left[i].clone();
            i += 1;
        } else {
            dest[k] = right[j].clone();
            j += 1;
        }
        k += 1;
    }

    while i < left.len() {
        dest[k] = left[i].clone();
        i += 1;
        k += 1;
    }

    while j < right.len() {
        dest[k] = right[j].clone();
        j += 1;
        k += 1;
    }
}

/// Heap Sort
///
/// Uses a binary heap data structure. First builds a max heap, then
/// repeatedly extracts the maximum element and places it at the end.
///
/// # Performance
///
/// - Best/Average/Worst: O(n log n)
/// - Space: O(1) - in-place
/// - Stable: No
///
/// # Examples
///
/// ```
/// use rlab::common::sort::heap_sort;
///
/// let mut arr = [12, 11, 13, 5, 6, 7];
/// heap_sort(&mut arr);
/// assert_eq!(arr, [5, 6, 7, 11, 12, 13]);
/// ```
pub fn heap_sort<T: Ord>(arr: &mut [T]) {
    let n = arr.len();
    if n <= 1 {
        return;
    }

    // Build max heap
    // Start from last non-leaf node and heapify each
    for i in (0..n / 2).rev() {
        heapify(arr, n, i);
    }

    // Extract elements from heap one by one
    for i in (1..n).rev() {
        // Move current root (max) to end
        arr.swap(0, i);
        // Heapify the reduced heap
        heapify(arr, i, 0);
    }
}

/// Heapify subtree rooted at index i
/// n is size of heap
fn heapify<T: Ord>(arr: &mut [T], n: usize, i: usize) {
    let mut largest = i;
    let left = 2 * i + 1;
    let right = 2 * i + 2;

    // Find largest among root, left child and right child
    if left < n && arr[left] > arr[largest] {
        largest = left;
    }

    if right < n && arr[right] > arr[largest] {
        largest = right;
    }

    // If largest is not root, swap and continue heapifying
    if largest != i {
        arr.swap(i, largest);
        heapify(arr, n, largest);
    }
}

/// Heap Sort using std::collections::BinaryHeap
///
/// Simpler implementation using Rust's standard library heap.
/// Less efficient due to allocation overhead but demonstrates
/// using standard library data structures.
pub fn heap_sort_std<T: Ord + Clone>(arr: &mut [T]) {
    let n = arr.len();
    if n <= 1 {
        return;
    }

    // Use Reverse for min-heap behavior
    let mut heap: BinaryHeap<Reverse<T>> = arr.iter().cloned().map(Reverse).collect();

    // Extract elements in sorted order
    for i in 0..n {
        if let Some(Reverse(val)) = heap.pop() {
            arr[i] = val;
        }
    }
}

/// Tim Sort (Hybrid)
///
/// Hybrid sorting algorithm derived from merge sort and insertion sort.
/// Used as the default sorting algorithm in Python and Java.
///
/// This is a simplified implementation. Real timsort is more complex
/// with galloping mode and sophisticated merge strategies.
///
/// # Performance
///
/// - Best: O(n) on already sorted data
/// - Average/Worst: O(n log n)
/// - Space: O(n)
/// - Stable: Yes
const RUN: usize = 32; // Minimum run size

/// Run tim sort on the array
pub fn tim_sort<T: Ord + Clone>(arr: &mut [T]) {
    let n = arr.len();
    if n <= 1 {
        return;
    }

    // Sort individual subarrays of size RUN using insertion sort
    for start in (0..n).step_by(RUN) {
        let end = (start + RUN).min(n);
        insertion_sort_range(arr, start, end);
    }

    // Start merging from size RUN (or 32)
    let mut size = RUN;
    while size < n {
        for left in (0..n).step_by(2 * size) {
            let mid = (left + size).min(n);
            let right = (left + 2 * size).min(n);

            if mid < right {
                merge_inplace(arr, left, mid, right);
            }
        }
        size *= 2;
    }
}

/// Insertion sort for a range within the array
fn insertion_sort_range<T: Ord>(arr: &mut [T], start: usize, end: usize) {
    for i in start + 1..end {
        let mut j = i;
        while j > start && arr[j - 1] > arr[j] {
            arr.swap(j - 1, j);
            j -= 1;
        }
    }
}

/// Merge two adjacent sorted ranges [left..mid) and [mid..right)
fn merge_inplace<T: Ord + Clone>(arr: &mut [T], left: usize, mid: usize, right: usize) {
    let left_slice = arr[left..mid].to_vec();
    let right_slice = arr[mid..right].to_vec();

    let (mut i, mut j, mut k) = (0, 0, left);

    while i < left_slice.len() && j < right_slice.len() {
        if left_slice[i] <= right_slice[j] {
            arr[k] = left_slice[i].clone();
            i += 1;
        } else {
            arr[k] = right_slice[j].clone();
            j += 1;
        }
        k += 1;
    }

    while i < left_slice.len() {
        arr[k] = left_slice[i].clone();
        i += 1;
        k += 1;
    }

    while j < right_slice.len() {
        arr[k] = right_slice[j].clone();
        j += 1;
        k += 1;
    }
}

/// Intro Sort (Introspective Sort)
///
/// Hybrid algorithm that combines quicksort, heapsort, and insertion sort.
/// - Uses quicksort for small recursion depth
/// - Switches to heapsort when recursion depth exceeds limit (guarantees O(n log n))
/// - Uses insertion sort for small subarrays
///
/// This is the algorithm typically used by std::sort in C++.
const INTRO_THRESHOLD: usize = 16;

/// Run intro sort on the array
pub fn intro_sort<T: Ord>(arr: &mut [T]) {
    let n = arr.len();
    if n <= 1 {
        return;
    }

    // Maximum recursion depth: 2 * floor(log2(n))
    let max_depth = 2 * (n as f64).log2() as usize;
    intro_sort_helper(arr, max_depth);
}

fn intro_sort_helper<T: Ord>(arr: &mut [T], max_depth: usize) {
    let n = arr.len();
    if n <= INTRO_THRESHOLD {
        insertion_sort_small(arr);
        return;
    }

    if max_depth == 0 {
        // Switch to heapsort to guarantee O(n log n)
        heap_sort(arr);
        return;
    }

    // Use quicksort with median-of-three pivot
    let pivot = median_of_three(arr);
    arr.swap(pivot, n - 1);

    let p = partition_intro(arr);

    intro_sort_helper(&mut arr[0..p], max_depth - 1);
    intro_sort_helper(&mut arr[p + 1..n], max_depth - 1);
}

fn median_of_three<T: Ord>(arr: &mut [T]) -> usize {
    let n = arr.len();
    let mid = n / 2;
    let last = n - 1;

    if arr[0] > arr[mid] {
        arr.swap(0, mid);
    }
    if arr[0] > arr[last] {
        arr.swap(0, last);
    }
    if arr[mid] > arr[last] {
        arr.swap(mid, last);
    }

    mid
}

fn partition_intro<T: Ord>(arr: &mut [T]) -> usize {
    let n = arr.len();
    let pivot = n - 1;
    let mut i = 0;

    for j in 0..n - 1 {
        if arr[j] <= arr[pivot] {
            arr.swap(i, j);
            i += 1;
        }
    }

    arr.swap(i, pivot);
    i
}

fn insertion_sort_small<T: Ord>(arr: &mut [T]) {
    let n = arr.len();
    for i in 1..n {
        let mut j = i;
        while j > 0 && arr[j - 1] > arr[j] {
            arr.swap(j - 1, j);
            j -= 1;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn test_sort_fn<F>(sort_fn: F)
    where
        F: Fn(&mut [i32]),
    {
        // Empty
        let mut arr: [i32; 0] = [];
        sort_fn(&mut arr);
        assert_eq!(arr, []);

        // Single element
        let mut arr = [1];
        sort_fn(&mut arr);
        assert_eq!(arr, [1]);

        // Already sorted
        let mut arr = [1, 2, 3, 4, 5];
        sort_fn(&mut arr);
        assert_eq!(arr, [1, 2, 3, 4, 5]);

        // Reverse sorted
        let mut arr = [5, 4, 3, 2, 1];
        sort_fn(&mut arr);
        assert_eq!(arr, [1, 2, 3, 4, 5]);

        // Random
        let mut arr = [38, 27, 43, 3, 9, 82, 10];
        sort_fn(&mut arr);
        assert_eq!(arr, [3, 9, 10, 27, 38, 43, 82]);

        // Duplicates
        let mut arr = [3, 1, 4, 1, 5, 9, 2, 6, 5];
        sort_fn(&mut arr);
        assert_eq!(arr, [1, 1, 2, 3, 4, 5, 5, 6, 9]);
    }

    #[test]
    fn test_merge_sort() {
        test_sort_fn(merge_sort);
    }

    #[test]
    fn test_merge_sort_bottom_up() {
        test_sort_fn(merge_sort_bottom_up);
    }

    #[test]
    fn test_heap_sort() {
        test_sort_fn(heap_sort);
    }

    #[test]
    fn test_heap_sort_std() {
        test_sort_fn(heap_sort_std);
    }

    #[test]
    fn test_tim_sort() {
        test_sort_fn(tim_sort);
    }

    #[test]
    fn test_intro_sort() {
        test_sort_fn(intro_sort);
    }

    #[test]
    fn test_large_merge_sort() {
        let mut arr: Vec<i32> = (0..1000).rev().collect();
        merge_sort(&mut arr);
        assert!(arr.windows(2).all(|w| w[0] <= w[1]));
    }

    #[test]
    fn test_stability_merge_sort() {
        // Test that merge sort preserves order of equal elements
        let mut arr = vec![(1, "a"), (2, "b"), (1, "c"), (2, "d")];
        merge_sort(&mut arr);
        assert_eq!(arr, vec![(1, "a"), (1, "c"), (2, "b"), (2, "d")]);
    }
}
