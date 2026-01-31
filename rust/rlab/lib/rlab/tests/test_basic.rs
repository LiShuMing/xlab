//! Basic Rust concepts tests
//!
//! These tests demonstrate fundamental Rust concepts:
//! - Ownership and borrowing
//! - Lifetimes
//! - Drop trait behavior

use rlab::add;

#[test]
fn test_lib_add() {
    let result = add(2, 2);
    assert_eq!(result, 4);
}

#[test]
fn test_ownership_clone() {
    let s = String::from("hello");
    let s2 = s.clone();
    
    // Both s and s2 are valid because we cloned
    assert_eq!(s, "hello");
    assert_eq!(s2, "hello");
}

#[test]
fn test_ownership_mutable_borrow() {
    let mut s = String::from("hello");
    
    {
        let s2 = &mut s;
        s2.push_str(" world");
        assert_eq!(*s2, "hello world");
    }
    // s2 is out of scope, so we can use s again
    
    assert_eq!(s, "hello world");
}

#[test]
fn test_reference_borrowing() {
    let mut s = String::from("hello");
    let s2 = &mut s;
    
    // Can read through mutable reference
    assert_eq!(s2, "hello");
    
    // Modify through the reference
    s2.push_str("!");
    assert_eq!(s2, "hello!");
}

#[test]
fn test_clone_behavior() {
    let s3 = String::from("hello");
    let s4 = s3.clone();
    
    // Both are valid after clone
    assert_eq!(s3, "hello");
    assert_eq!(s4, "hello");
}

/// Demonstrates passing references to functions
fn compute(a: &u32, output: &mut u32) {
    if *a > 10 {
        *output = *a + 1;
    } else {
        *output = *a - 1;
    }
}

#[test]
fn test_compute_function() {
    let a = 11;
    let mut output = 0;
    compute(&a, &mut output);
    assert_eq!(output, 12);
    
    let a = 5;
    let mut output = 0;
    compute(&a, &mut output);
    assert_eq!(output, 4);
}

/// Demonstrates vector behavior with copy types
#[test]
fn test_vec_and_copy() {
    let mut data = vec![1, 2, 3];
    let x = data[0]; // i32 is Copy, so this copies the value
    data.push(4);    // We can still use data
    
    assert_eq!(x, 1);
    assert_eq!(data, vec![1, 2, 3, 4]);
}

// Structs for demonstrating Drop order
#[derive(Debug)]
struct X<'a>(&'a i32);

#[derive(Debug)]
struct Y<'a>(&'a i32);

impl Drop for X<'_> {
    fn drop(&mut self) {
        // In real code, this would print
        // println!("Dropping X");
    }
}

impl Drop for Y<'_> {
    fn drop(&mut self) {
        // In real code, this would print
        // println!("Dropping Y");
    }
}

#[test]
fn test_drop_order() {
    let data = vec![1, 2, 3];
    {
        let x = X(&data[0]);
        let y = Y(&data[1]);
        
        // Use them to avoid warnings
        assert_eq!(*x.0, 1);
        assert_eq!(*y.0, 2);
        
        // y is dropped first (LIFO order), then x
    }
    // Can use data again after borrows end
    assert_eq!(data.len(), 3);
}

/// Demonstrates self-referential struct pattern
#[derive(Debug)]
struct Foo;

impl Foo {
    fn mut_and_share<'a>(&'a mut self) -> &'a mut Self {
        &mut *self
    }
    
    fn share<'a>(&'a self) -> &'a Self {
        self
    }
}

#[test]
fn test_self_referential() {
    let mut foo = Foo;
    let mut_foo = foo.mut_and_share();
    
    // Use the reference
    let _ = format!("{:?}", mut_foo);
    
    // After mut_foo is dropped, we can borrow foo again
    drop(mut_foo);
    let _shared = foo.share();
    let _ = _shared;
}
