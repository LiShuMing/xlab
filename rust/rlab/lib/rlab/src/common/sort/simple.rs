//! Simple O(n²) sorting algorithms
//!
//! These algorithms are suitable for small datasets or educational purposes.
//! They have worse time complexity than O(n log n) algorithms but are
//! simple to understand and implement.

/// Bubble Sort
///
/// Repeatedly steps through the list, compares adjacent elements and swaps them
/// if they are in the wrong order. The pass through the list is repeated until
/// the list is sorted.
///
/// # Performance
///
/// - Best: O(n) when array is already sorted
/// - Average/Worst: O(n²)
/// - Space: O(1)
///
/// # Examples
///
/// ```
/// use rlab::common::sort::bubble_sort;
///
/// let mut arr = [64, 34, 25, 12, 22, 11, 90];
/// bubble_sort(&mut arr);
/// assert_eq!(arr, [11, 12, 22, 25, 34, 64, 90]);
/// ```
pub fn bubble_sort<T: Ord>(arr: &mut [T]) {
    let n = arr.len();
    if n <= 1 {
        return;
    }

    for i in 0..n {
        // Flag to detect if any swap occurred in this pass
        let mut swapped = false;

        // Last i elements are already in place
        for j in 0..n - i - 1 {
            if arr[j] > arr[j + 1] {
                arr.swap(j, j + 1);
                swapped = true;
            }
        }

        // If no swaps occurred, array is sorted
        if !swapped {
            break;
        }
    }
}

/// Selection Sort
///
/// Divides the array into a sorted and unsorted region. Repeatedly selects
/// the minimum element from the unsorted region and moves it to the end
/// of the sorted region.
///
/// # Performance
///
/// - Best/Average/Worst: O(n²)
/// - Space: O(1)
/// - Performs minimal writes (O(n) swaps)
///
/// # Examples
///
/// ```
/// use rlab::common::sort::selection_sort;
///
/// let mut arr = [64, 25, 12, 22, 11];
/// selection_sort(&mut arr);
/// assert_eq!(arr, [11, 12, 22, 25, 64]);
/// ```
pub fn selection_sort<T: Ord>(arr: &mut [T]) {
    let n = arr.len();
    if n <= 1 {
        return;
    }

    for i in 0..n {
        // Find the minimum element in the unsorted portion
        let mut min_idx = i;
        for j in i + 1..n {
            if arr[j] < arr[min_idx] {
                min_idx = j;
            }
        }

        // Swap the found minimum with the first element of unsorted portion
        if min_idx != i {
            arr.swap(i, min_idx);
        }
    }
}

/// Insertion Sort
///
/// Builds the sorted array one element at a time by repeatedly taking
/// the next element and inserting it into the correct position in the
/// already-sorted portion.
///
/// Efficient for small datasets and nearly-sorted data.
///
/// # Performance
///
/// - Best: O(n) when array is already sorted
/// - Average/Worst: O(n²)
/// - Space: O(1)
///
/// # Examples
///
/// ```
/// use rlab::common::sort::insertion_sort;
///
/// let mut arr = [12, 11, 13, 5, 6];
/// insertion_sort(&mut arr);
/// assert_eq!(arr, [5, 6, 11, 12, 13]);
/// ```
pub fn insertion_sort<T: Ord>(arr: &mut [T]) {
    let n = arr.len();
    if n <= 1 {
        return;
    }

    for i in 1..n {
        // Move elements greater than arr[i] one position ahead
        // to make room for inserting arr[i] in the correct position
        let mut j = i;
        while j > 0 && arr[j - 1] > arr[j] {
            arr.swap(j - 1, j);
            j -= 1;
        }
    }
}

/// Optimized Insertion Sort with binary search
///
/// Uses binary search to find the insertion position, reducing the number
/// of comparisons from O(n) to O(log n) per element.
///
/// Note: The number of swaps remains O(n), so overall complexity is still O(n²).
pub fn insertion_sort_binary<T: Ord>(arr: &mut [T]) {
    let n = arr.len();
    if n <= 1 {
        return;
    }

    for i in 1..n {
        // Binary search for insertion point
        let insert_pos = binary_search_insert_pos(&arr[0..i], &arr[i]);

        // Shift elements and insert
        let mut j = i;
        while j > insert_pos {
            arr.swap(j - 1, j);
            j -= 1;
        }
    }
}

/// Find the position where `key` should be inserted in sorted `arr`
fn binary_search_insert_pos<T: Ord>(arr: &[T], key: &T) -> usize {
    let mut left = 0;
    let mut right = arr.len();

    while left < right {
        let mid = left + (right - left) / 2;
        if arr[mid] < *key {
            left = mid + 1;
        } else {
            right = mid;
        }
    }

    left
}

/// Shell Sort
///
/// Generalization of insertion sort that allows exchange of far-apart elements.
/// Starts with a large gap and reduces it until gap = 1.
///
/// # Performance
///
/// - Depends on gap sequence (typically O(n^(3/2)) or better)
/// - Space: O(1)
///
/// # Examples
///
/// ```
/// use rlab::common::sort::shell_sort;
///
/// let mut arr = [12, 34, 54, 2, 3];
/// shell_sort(&mut arr);
/// assert_eq!(arr, [2, 3, 12, 34, 54]);
/// ```
pub fn shell_sort<T: Ord>(arr: &mut [T]) {
    let n = arr.len();
    if n <= 1 {
        return;
    }

    // Using Knuth's sequence: 1, 4, 13, 40, 121, ...
    let mut gap = 1;
    while gap < n / 3 {
        gap = 3 * gap + 1;
    }

    while gap >= 1 {
        // Do insertion sort for elements at gap distance
        for i in gap..n {
            let mut j = i;
            while j >= gap && arr[j - gap] > arr[j] {
                arr.swap(j - gap, j);
                j -= gap;
            }
        }
        gap /= 3;
    }
}

/// Gnome Sort (Stupid Sort)
///
/// Similar to insertion sort but moves elements back to their proper position
/// by a series of swaps, like a garden gnome sorting flower pots.
///
/// # Performance
///
/// - Best: O(n)
/// - Average/Worst: O(n²)
/// - Space: O(1)
pub fn gnome_sort<T: Ord>(arr: &mut [T]) {
    let n = arr.len();
    if n <= 1 {
        return;
    }

    let mut pos = 0;
    while pos < n {
        if pos == 0 || arr[pos] >= arr[pos - 1] {
            pos += 1;
        } else {
            arr.swap(pos, pos - 1);
            pos -= 1;
        }
    }
}

/// Comb Sort
///
/// Improvement over bubble sort that eliminates "turtles" (small values near the end)
/// by using a gap larger than 1 initially, then shrinking to 1.
///
/// # Performance
///
/// - Average: O(n² / 2^p) where p is the number of increments
/// - Worst: O(n²)
/// - Best: O(n log n)
/// - Space: O(1)
pub fn comb_sort<T: Ord>(arr: &mut [T]) {
    let n = arr.len();
    if n <= 1 {
        return;
    }

    let shrink_factor = 1.3;
    let mut gap = n;
    let mut sorted = false;

    while !sorted {
        // Update gap
        gap = (gap as f64 / shrink_factor) as usize;
        if gap <= 1 {
            gap = 1;
            sorted = true;
        }

        // Compare elements gap apart
        for i in 0..n - gap {
            if arr[i] > arr[i + gap] {
                arr.swap(i, i + gap);
                sorted = false;
            }
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
        let mut arr = [64, 34, 25, 12, 22, 11, 90];
        sort_fn(&mut arr);
        assert_eq!(arr, [11, 12, 22, 25, 34, 64, 90]);

        // Duplicates
        let mut arr = [3, 1, 4, 1, 5, 9, 2, 6, 5];
        sort_fn(&mut arr);
        assert_eq!(arr, [1, 1, 2, 3, 4, 5, 5, 6, 9]);
    }

    #[test]
    fn test_bubble_sort() {
        test_sort_fn(bubble_sort);
    }

    #[test]
    fn test_selection_sort() {
        test_sort_fn(selection_sort);
    }

    #[test]
    fn test_insertion_sort() {
        test_sort_fn(insertion_sort);
    }

    #[test]
    fn test_insertion_sort_binary() {
        test_sort_fn(insertion_sort_binary);
    }

    #[test]
    fn test_shell_sort() {
        test_sort_fn(shell_sort);
    }

    #[test]
    fn test_gnome_sort() {
        test_sort_fn(gnome_sort);
    }

    #[test]
    fn test_comb_sort() {
        test_sort_fn(comb_sort);
    }
}
