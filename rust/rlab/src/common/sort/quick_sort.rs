//! Quick Sort Implementation
//! 
//! This module demonstrates:
//! - Generic programming with trait bounds
//! - In-place sorting algorithms
//! - Recursive algorithms in Rust
//! - Proper use of slices and indices

/// Sorts a slice in-place using the quicksort algorithm.
///
/// # Examples
///
/// ```
/// let mut numbers = [3, 1, 4, 1, 5, 9, 2, 6];
/// rlab::common::sort::quick_sort::quick_sort(&mut numbers);
/// assert_eq!(numbers, [1, 1, 2, 3, 4, 5, 6, 9]);
/// ```
///
/// # Performance
///
/// - Best/Average: O(n log n)
/// - Worst: O(n²) - can be mitigated with random pivot selection
/// - Space: O(log n) due to recursion
pub fn quick_sort<T: Ord>(arr: &mut [T]) {
    if arr.len() <= 1 {
        return;
    }
    let len = arr.len();
    _quick_sort(arr, 0, len - 1);
}

/// Internal recursive quicksort function.
/// 
/// Uses `usize` indices rather than `isize` for type safety,
/// with careful bounds checking.
fn _quick_sort<T: Ord>(arr: &mut [T], low: usize, high: usize) {
    if low < high {
        let p = partition(arr, low, high);
        
        // Recursively sort elements before and after partition
        // We need to be careful about underflow when p is 0
        if p > 0 {
            _quick_sort(arr, low, p - 1);
        }
        _quick_sort(arr, p + 1, high);
    }
}

/// Partitions the array around a pivot (last element).
/// 
/// Returns the final index of the pivot element.
fn partition<T: Ord>(arr: &mut [T], low: usize, high: usize) -> usize {
    // Choose the last element as pivot
    let pivot_index = high;
    let mut i = low;
    
    // Move all elements smaller than pivot to the left
    for j in low..high {
        if arr[j] <= arr[pivot_index] {
            arr.swap(i, j);
            i += 1;
        }
    }
    
    // Place pivot in its correct position
    arr.swap(i, pivot_index);
    i
}

/// Sorts a slice using a randomized pivot for better average performance.
/// 
/// This variant helps avoid worst-case O(n²) performance on already sorted arrays.
#[allow(dead_code)]
pub fn quick_sort_random<T: Ord>(arr: &mut [T]) {
    use std::cell::RefCell;
    
    thread_local! {
        static RNG: RefCell<fastrand::Rng> = RefCell::new(fastrand::Rng::new());
    }
    
    fn _quick_sort_random<T: Ord>(arr: &mut [T], low: usize, high: usize) {
        if low < high {
            let p = partition_random(arr, low, high, &mut || {
                RNG.with(|rng| rng.borrow_mut().usize(low..=high))
            });
            
            if p > 0 {
                _quick_sort_random(arr, low, p - 1);
            }
            if p < high {
                _quick_sort_random(arr, p + 1, high);
            }
        }
    }
    
    fn partition_random<T: Ord, F: FnMut() -> usize>(
        arr: &mut [T], 
        low: usize, 
        high: usize,
        rng: &mut F
    ) -> usize {
        // Choose random pivot and swap with last element
        let pivot_idx = rng();
        arr.swap(pivot_idx, high);
        
        let mut i = low;
        for j in low..high {
            if arr[j] <= arr[high] {
                arr.swap(i, j);
                i += 1;
            }
        }
        arr.swap(i, high);
        i
    }
    
    if arr.len() <= 1 {
        return;
    }
    let len = arr.len();
    _quick_sort_random(arr, 0, len - 1);
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_empty() {
        let mut arr: [i32; 0] = [];
        quick_sort(&mut arr);
        assert_eq!(arr, []);
    }

    #[test]
    fn test_single_element() {
        let mut arr = [42];
        quick_sort(&mut arr);
        assert_eq!(arr, [42]);
    }

    #[test]
    fn test_already_sorted() {
        let mut arr = [1, 2, 3, 4, 5];
        quick_sort(&mut arr);
        assert_eq!(arr, [1, 2, 3, 4, 5]);
    }

    #[test]
    fn test_reverse_sorted() {
        let mut arr = [5, 4, 3, 2, 1];
        quick_sort(&mut arr);
        assert_eq!(arr, [1, 2, 3, 4, 5]);
    }

    #[test]
    fn test_basic_sort() {
        let mut numbers = [4, 65, 2, -31, 0, 99, 2, 83, 782, 1];
        quick_sort(&mut numbers);
        assert_eq!(numbers, [-31, 0, 1, 2, 2, 4, 65, 83, 99, 782]);
    }

    #[test]
    fn test_duplicates() {
        let mut arr = [3, 3, 3, 1, 1, 2, 2];
        quick_sort(&mut arr);
        assert_eq!(arr, [1, 1, 2, 2, 3, 3, 3]);
    }

    #[test]
    fn test_strings() {
        let mut words = ["banana", "apple", "cherry", "date"];
        quick_sort(&mut words);
        assert_eq!(words, ["apple", "banana", "cherry", "date"]);
    }
}
