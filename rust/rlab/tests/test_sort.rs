//! Integration tests for sorting algorithms
//!
//! These tests verify the correctness of sorting implementations
//! and demonstrate how to use them as a library.

use rlab::common::sort::{is_sorted, quick_sort};

#[test]
fn test_quick_sort_basic() {
    let mut numbers = [4, 65, 2, -31, 0, 99, 2, 83, 782, 1];
    quick_sort(&mut numbers);
    assert_eq!(numbers, [-31, 0, 1, 2, 2, 4, 65, 83, 99, 782]);
    assert!(is_sorted(&numbers));
}

#[test]
fn test_quick_sort_empty() {
    let mut arr: [i32; 0] = [];
    quick_sort(&mut arr);
    assert!(is_sorted(&arr));
}

#[test]
fn test_quick_sort_single() {
    let mut arr = [42];
    quick_sort(&mut arr);
    assert_eq!(arr, [42]);
    assert!(is_sorted(&arr));
}

#[test]
fn test_quick_sort_already_sorted() {
    let mut arr = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
    quick_sort(&mut arr);
    assert_eq!(arr, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
    assert!(is_sorted(&arr));
}

#[test]
fn test_quick_sort_reverse_sorted() {
    let mut arr = [10, 9, 8, 7, 6, 5, 4, 3, 2, 1];
    quick_sort(&mut arr);
    assert_eq!(arr, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
    assert!(is_sorted(&arr));
}

#[test]
fn test_quick_sort_all_equal() {
    let mut arr = [5, 5, 5, 5, 5];
    quick_sort(&mut arr);
    assert_eq!(arr, [5, 5, 5, 5, 5]);
    assert!(is_sorted(&arr));
}

#[test]
fn test_quick_sort_strings() {
    let mut words = ["banana", "apple", "cherry", "date", "elderberry"];
    quick_sort(&mut words);
    assert_eq!(words, ["apple", "banana", "cherry", "date", "elderberry"]);
    assert!(is_sorted(&words));
}

#[test]
fn test_quick_sort_chars() {
    let mut chars = ['z', 'a', 'm', 'b', 'c'];
    quick_sort(&mut chars);
    assert_eq!(chars, ['a', 'b', 'c', 'm', 'z']);
    assert!(is_sorted(&chars));
}

#[test]
fn test_is_sorted_various() {
    assert!(is_sorted::<i32>(&[]));
    assert!(is_sorted(&[1]));
    assert!(is_sorted(&[1, 2, 3, 4, 5]));
    assert!(is_sorted(&[1, 1, 1, 1]));
    
    assert!(!is_sorted(&[5, 4, 3, 2, 1]));
    assert!(!is_sorted(&[1, 3, 2, 4, 5]));
}

#[test]
fn test_large_sort() {
    let mut arr: Vec<i32> = (0..1000).rev().collect();
    quick_sort(&mut arr);
    
    assert!(is_sorted(&arr));
    assert_eq!(arr[0], 0);
    assert_eq!(arr[999], 999);
}
