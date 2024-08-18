//! Sorting algorithms collection
//!
//! This module provides various sorting implementations for learning purposes.
//! Each algorithm demonstrates different Rust concepts and trade-offs.
//!
//! # Algorithm Categories
//!
//! ## Simple O(n²) Algorithms
//! - [`bubble_sort`] - Educational, detects already sorted
//! - [`selection_sort`] - Minimal writes
//! - [`insertion_sort`] - Good for small/nearly-sorted data
//! - [`shell_sort`] - Improvement over insertion sort
//! - [`gnome_sort`] - Simple, one-pass approach
//! - [`comb_sort`] - Eliminates "turtles"
//!
//! ## Efficient O(n log n) Algorithms
//! - [`quick_sort`] - Fast in practice, in-place
//! - [`merge_sort`] - Stable, predictable performance
//! - [`heap_sort`] - In-place, guaranteed O(n log n)
//! - [`tim_sort`] - Hybrid (merge + insertion), used by Python/Java
//! - [`intro_sort`] - Hybrid (quick + heap + insertion), used by C++
//!
//! ## Linear Time O(n) Algorithms (Integers)
//! - [`counting_sort`] - Small integer range
//! - [`radix_sort_lsd`] - Base-256 LSD radix sort
//! - [`radix_sort_msd`] - Base-256 MSD radix sort
//! - [`bucket_sort`] - Uniform distribution
//! - [`flash_sort`] - Near-uniform distribution
//!
//! # Performance Comparison
//!
//! | Algorithm | Best | Average | Worst | Space | Stable |
//! |-----------|------|---------|-------|-------|--------|
//! | Bubble | O(n) | O(n²) | O(n²) | O(1) | Yes |
//! | Selection | O(n²) | O(n²) | O(n²) | O(1) | No |
//! | Insertion | O(n) | O(n²) | O(n²) | O(1) | Yes |
//! | Shell | O(n log n) | O(n^1.3) | O(n²) | O(1) | No |
//! | Quick | O(n log n) | O(n log n) | O(n²) | O(log n) | No |
//! | Merge | O(n log n) | O(n log n) | O(n log n) | O(n) | Yes |
//! | Heap | O(n log n) | O(n log n) | O(n log n) | O(1) | No |
//! | Counting | O(n+k) | O(n+k) | O(n+k) | O(n+k) | Yes |
//! | Radix | O(d(n+b)) | O(d(n+b)) | O(d(n+b)) | O(n+b) | Yes |
//!
//! # Examples
//!
//! ```
//! use rlab::common::sort::quick_sort;
//!
//! let mut numbers = [3, 1, 4, 1, 5, 9, 2, 6];
//! quick_sort(&mut numbers);
//! assert_eq!(numbers, [1, 1, 2, 3, 4, 5, 6, 9]);
//! ```

pub mod benchmark;
pub mod efficient;
pub mod integer;
pub mod quick_sort;
pub mod simple;

// Re-export simple sorts
pub use simple::{
    bubble_sort, comb_sort, gnome_sort, insertion_sort, insertion_sort_binary, selection_sort,
    shell_sort,
};

// Re-export efficient sorts
pub use efficient::{heap_sort, intro_sort, merge_sort, merge_sort_bottom_up, tim_sort};

// Re-export quick sort
pub use quick_sort::quick_sort;

// Re-export integer sorts
pub use integer::{
    bucket_sort, counting_sort, counting_sort_by_key, flash_sort, radix_sort_lsd, radix_sort_msd,
};

/// Checks if a slice is sorted in ascending order.
///
/// # Examples
///
/// ```
/// use rlab::common::sort::is_sorted;
///
/// assert!(is_sorted(&[1, 2, 3, 4, 5]));
/// assert!(!is_sorted(&[5, 4, 3, 2, 1]));
/// assert!(is_sorted::<i32>(&[]));
/// ```
pub fn is_sorted<T: Ord>(slice: &[T]) -> bool {
    slice.windows(2).all(|w| w[0] <= w[1])
}

/// Checks if a slice is sorted in descending order.
pub fn is_sorted_desc<T: Ord>(slice: &[T]) -> bool {
    slice.windows(2).all(|w| w[0] >= w[1])
}

/// Reverses a slice in-place.
///
/// # Examples
///
/// ```
/// use rlab::common::sort::reverse;
///
/// let mut arr = [1, 2, 3, 4, 5];
/// reverse(&mut arr);
/// assert_eq!(arr, [5, 4, 3, 2, 1]);
/// ```
pub fn reverse<T>(arr: &mut [T]) {
    let n = arr.len();
    for i in 0..n / 2 {
        arr.swap(i, n - i - 1);
    }
}

/// Generates a random array of the given size using a seeded RNG.
/// Generate random array for benchmarking
pub fn generate_random_array(size: usize, max_val: i32) -> Vec<i32> {
    use std::cell::RefCell;

    thread_local! {
        static RNG: RefCell<fastrand::Rng> = RefCell::new(fastrand::Rng::new());
    }

    RNG.with(|rng| {
        let mut rng = rng.borrow_mut();
        (0..size).map(|_| rng.i32(0..max_val)).collect()
    })
}

/// Generates a sorted array.
pub fn generate_sorted_array(size: usize) -> Vec<i32> {
    (0..size as i32).collect()
}

/// Generates a reverse sorted array.
pub fn generate_reverse_array(size: usize) -> Vec<i32> {
    (0..size as i32).rev().collect()
}

/// Generates an array with many duplicates.
/// Generate array with few unique values
pub fn generate_few_unique_array(size: usize, unique_values: usize) -> Vec<i32> {
    use std::cell::RefCell;

    thread_local! {
        static RNG: RefCell<fastrand::Rng> = RefCell::new(fastrand::Rng::new());
    }

    RNG.with(|rng| {
        let mut rng = rng.borrow_mut();
        (0..size)
            .map(|_| rng.i32(0..unique_values as i32))
            .collect()
    })
}

/// Generates a nearly sorted array (10% of elements out of place).
/// Generate nearly sorted array
pub fn generate_nearly_sorted_array(size: usize) -> Vec<i32> {
    use std::cell::RefCell;

    thread_local! {
        static RNG: RefCell<fastrand::Rng> = RefCell::new(fastrand::Rng::new());
    }

    let mut arr: Vec<i32> = (0..size as i32).collect();

    RNG.with(|rng| {
        let mut rng = rng.borrow_mut();
        let swaps = size / 10;
        for _ in 0..swaps {
            let i = rng.usize(0..size);
            let j = rng.usize(0..size);
            arr.swap(i, j);
        }
    });

    arr
}

/// Sort algorithm descriptor
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum SortAlgorithm {
    /// Bubble sort - O(n²)
    Bubble,
    /// Selection sort - O(n²)
    Selection,
    /// Insertion sort - O(n²)
    Insertion,
    /// Shell sort - O(n^1.3)
    Shell,
    /// Gnome sort - O(n²)
    Gnome,
    /// Comb sort - O(n² / 2^p)
    Comb,
    /// Quick sort - O(n log n) avg
    Quick,
    /// Merge sort - O(n log n)
    Merge,
    /// Heap sort - O(n log n)
    Heap,
    /// Tim sort - O(n log n)
    Tim,
    /// Intro sort - O(n log n)
    Intro,
    /// Counting sort - O(n+k)
    Counting,
    /// Radix sort (LSD) - O(d(n+b))
    RadixLsd,
    /// Radix sort (MSD) - O(d(n+b))
    RadixMsd,
    /// Bucket sort - O(n+k) avg
    Bucket,
    /// Flash sort - O(n) avg
    Flash,
}

impl SortAlgorithm {
    /// Returns all available algorithms
    pub fn all() -> &'static [SortAlgorithm] {
        use SortAlgorithm::*;
        &[
            Bubble, Selection, Insertion, Shell, Gnome, Comb, Quick, Merge, Heap, Tim, Intro,
            Counting, RadixLsd, RadixMsd, Bucket, Flash,
        ]
    }

    /// Returns algorithms suitable for general-purpose sorting
    pub fn general_purpose() -> &'static [SortAlgorithm] {
        use SortAlgorithm::*;
        &[Quick, Merge, Heap, Tim, Intro]
    }

    /// Returns simple O(n²) algorithms
    pub fn simple() -> &'static [SortAlgorithm] {
        use SortAlgorithm::*;
        &[Bubble, Selection, Insertion, Shell, Gnome, Comb]
    }

    /// Returns integer-specific algorithms
    pub fn integer_only() -> &'static [SortAlgorithm] {
        use SortAlgorithm::*;
        &[Counting, RadixLsd, RadixMsd, Bucket, Flash]
    }

    /// Get the name of the algorithm
    pub fn name(&self) -> &'static str {
        use SortAlgorithm::*;
        match self {
            Bubble => "Bubble Sort",
            Selection => "Selection Sort",
            Insertion => "Insertion Sort",
            Shell => "Shell Sort",
            Gnome => "Gnome Sort",
            Comb => "Comb Sort",
            Quick => "Quick Sort",
            Merge => "Merge Sort",
            Heap => "Heap Sort",
            Tim => "Tim Sort",
            Intro => "Intro Sort",
            Counting => "Counting Sort",
            RadixLsd => "Radix Sort (LSD)",
            RadixMsd => "Radix Sort (MSD)",
            Bucket => "Bucket Sort",
            Flash => "Flash Sort",
        }
    }

    /// Get short name/abbreviation
    pub fn short_name(&self) -> &'static str {
        use SortAlgorithm::*;
        match self {
            Bubble => "bubble",
            Selection => "selection",
            Insertion => "insertion",
            Shell => "shell",
            Gnome => "gnome",
            Comb => "comb",
            Quick => "quick",
            Merge => "merge",
            Heap => "heap",
            Tim => "tim",
            Intro => "intro",
            Counting => "counting",
            RadixLsd => "radix-lsd",
            RadixMsd => "radix-msd",
            Bucket => "bucket",
            Flash => "flash",
        }
    }

    /// Get time complexity description
    pub fn time_complexity(&self) -> &'static str {
        use SortAlgorithm::*;
        match self {
            Bubble => "O(n²)",
            Selection => "O(n²)",
            Insertion => "O(n²)",
            Shell => "O(n^1.3)",
            Gnome => "O(n²)",
            Comb => "O(n²/2^p)",
            Quick => "O(n log n)",
            Merge => "O(n log n)",
            Heap => "O(n log n)",
            Tim => "O(n log n)",
            Intro => "O(n log n)",
            Counting => "O(n+k)",
            RadixLsd => "O(d(n+b))",
            RadixMsd => "O(d(n+b))",
            Bucket => "O(n+k)",
            Flash => "O(n)",
        }
    }

    /// Get space complexity
    pub fn space_complexity(&self) -> &'static str {
        use SortAlgorithm::*;
        match self {
            Bubble => "O(1)",
            Selection => "O(1)",
            Insertion => "O(1)",
            Shell => "O(1)",
            Gnome => "O(1)",
            Comb => "O(1)",
            Quick => "O(log n)",
            Merge => "O(n)",
            Heap => "O(1)",
            Tim => "O(n)",
            Intro => "O(log n)",
            Counting => "O(n+k)",
            RadixLsd => "O(n+b)",
            RadixMsd => "O(n+b)",
            Bucket => "O(n+k)",
            Flash => "O(m)",
        }
    }

    /// Returns true if the algorithm is stable
    pub fn is_stable(&self) -> bool {
        use SortAlgorithm::*;
        matches!(
            self,
            Bubble | Insertion | Merge | Tim | Counting | RadixLsd | RadixMsd
        )
    }

    /// Returns true if the algorithm works with any Ord type
    pub fn is_generic(&self) -> bool {
        use SortAlgorithm::*;
        matches!(
            self,
            Bubble | Selection | Insertion | Shell | Gnome | Comb | Quick | Merge | Heap | Tim
                | Intro
        )
    }
}

impl std::fmt::Display for SortAlgorithm {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.name())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_is_sorted() {
        assert!(is_sorted::<i32>(&[]));
        assert!(is_sorted(&[1]));
        assert!(is_sorted(&[1, 2, 3, 4, 5]));
        assert!(is_sorted(&[1, 1, 1, 1]));

        assert!(!is_sorted(&[5, 4, 3, 2, 1]));
        assert!(!is_sorted(&[1, 3, 2, 4, 5]));
    }

    #[test]
    fn test_reverse() {
        let mut arr = [1, 2, 3, 4, 5];
        reverse(&mut arr);
        assert_eq!(arr, [5, 4, 3, 2, 1]);

        let mut arr = [1, 2, 3, 4];
        reverse(&mut arr);
        assert_eq!(arr, [4, 3, 2, 1]);

        let mut arr: [i32; 0] = [];
        reverse(&mut arr);
        assert_eq!(arr, []);

        let mut arr = [42];
        reverse(&mut arr);
        assert_eq!(arr, [42]);
    }

    #[test]
    fn test_generate_sorted_array() {
        let arr = generate_sorted_array(5);
        assert_eq!(arr, vec![0, 1, 2, 3, 4]);
        assert!(is_sorted(&arr));
    }

    #[test]
    fn test_generate_reverse_array() {
        let arr = generate_reverse_array(5);
        assert_eq!(arr, vec![4, 3, 2, 1, 0]);
        assert!(is_sorted_desc(&arr));
    }

    #[test]
    fn test_algorithm_names() {
        for alg in SortAlgorithm::all() {
            assert!(!alg.name().is_empty());
            assert!(!alg.short_name().is_empty());
            assert!(!alg.time_complexity().is_empty());
            assert!(!alg.space_complexity().is_empty());
        }
    }
}
