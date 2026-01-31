//! Integration tests for example utilities
//!
//! These tests demonstrate how to use the example utilities
//! and verify they work correctly as a library.

use rlab::examples::{is_big, abs_all, make_adder, THRESHOLD};
use std::borrow::Cow;

#[test]
fn test_is_big_with_threshold() {
    assert!(!is_big(THRESHOLD));
    assert!(!is_big(THRESHOLD - 1));
    assert!(is_big(THRESHOLD + 1));
}

#[test]
fn test_abs_all_no_clone_needed() {
    let slice = [0, 1, 2];
    let mut input = Cow::from(&slice[..]);
    
    abs_all(&mut input);
    
    // Should still be borrowed since no mutation was needed
    assert!(matches!(input, Cow::Borrowed(_)));
    assert_eq!(input.as_ref(), &[0, 1, 2]);
}

#[test]
fn test_abs_all_clones_when_needed() {
    let slice = [-1, 0, 1];
    let mut input = Cow::from(&slice[..]);
    
    abs_all(&mut input);
    
    // Should be owned since mutation was needed
    assert!(matches!(input, Cow::Owned(_)));
    assert_eq!(input.as_ref(), &[1, 0, 1]);
}

#[test]
fn test_abs_all_already_owned() {
    let mut input = Cow::from(vec![-5, -4, -3]);
    
    abs_all(&mut input);
    
    // Should still be owned
    assert!(matches!(input, Cow::Owned(_)));
    assert_eq!(input.as_ref(), &[5, 4, 3]);
}

#[test]
fn test_make_adder_basic() {
    let add_five = make_adder(5);
    assert_eq!(add_five(0), 6);  // 0 + 1 + 5
    assert_eq!(add_five(10), 16); // 10 + 1 + 5
    
    let add_zero = make_adder(0);
    assert_eq!(add_zero(5), 6);  // 5 + 1 + 0
}

#[test]
fn test_adder_closure_capture() {
    let captured_value = 100;
    let add_captured = make_adder(captured_value);
    
    // The closure captures captured_value
    assert_eq!(add_captured(0), 101);
}

#[test]
fn test_constant_exported() {
    // Verify the constant is exported and has expected value
    assert_eq!(THRESHOLD, 100);
}
