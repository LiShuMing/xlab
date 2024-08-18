//! Integration tests for library utilities
//!
//! These tests demonstrate how to use the library functions
//! and verify they work correctly.

use rlab::sort::{is_sorted, quick_sort, merge_sort, heap_sort};
use rlab::{add, factorial, gcd};

#[test]
fn test_basic_math_add() {
    assert_eq!(add(2, 2), 4);
    assert_eq!(add(0, 0), 0);
    assert_eq!(add(100, 200), 300);
}

#[test]
fn test_factorial_basic() {
    assert_eq!(factorial(0), 1);
    assert_eq!(factorial(1), 1);
    assert_eq!(factorial(5), 120);
    assert_eq!(factorial(10), 3_628_800);
}

#[test]
fn test_gcd_basic() {
    assert_eq!(gcd(48, 18), 6);
    assert_eq!(gcd(56, 98), 14);
    assert_eq!(gcd(101, 10), 1);
}

#[test]
fn test_sorting_algorithms() {
    // Test quick sort
    let mut arr = [3, 1, 4, 1, 5];
    quick_sort(&mut arr);
    assert!(is_sorted(&arr));
    
    // Test merge sort
    let mut arr = vec![5, 4, 3, 2, 1];
    merge_sort(&mut arr);
    assert!(is_sorted(&arr));
    
    // Test heap sort
    let mut arr = [9, 8, 7, 6, 5];
    heap_sort(&mut arr);
    assert!(is_sorted(&arr));
}

#[test]
fn test_sorting_with_duplicates() {
    let mut arr = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5];
    quick_sort(&mut arr);
    assert!(is_sorted(&arr));
    assert_eq!(arr, [1, 1, 2, 3, 3, 4, 5, 5, 5, 6, 9]);
}

#[test]
fn test_sorting_strings() {
    let mut words = ["banana", "apple", "cherry"];
    quick_sort(&mut words);
    assert!(is_sorted(&words));
    assert_eq!(words, ["apple", "banana", "cherry"]);
}
