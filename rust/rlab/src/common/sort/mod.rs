//! Sorting algorithms collection
//!
//! This module provides various sorting implementations for learning purposes.
//! Each algorithm demonstrates different Rust concepts and trade-offs.

pub mod quick_sort;

/// Re-export commonly used sorting functions
#[allow(unused_imports)]
pub use quick_sort::quick_sort;

/// Error type for sorting operations
#[derive(Debug, Clone, PartialEq, Eq)]
#[allow(dead_code)]
pub enum SortError {
    /// Input is too large for the algorithm
    InputTooLarge,
    /// Comparison function violated ordering requirements
    InvalidComparison,
}

impl std::fmt::Display for SortError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            SortError::InputTooLarge => write!(f, "input too large for sorting algorithm"),
            SortError::InvalidComparison => write!(f, "comparison function violated ordering requirements"),
        }
    }
}

impl std::error::Error for SortError {}

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
