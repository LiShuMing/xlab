//! Basic Rust learning examples
//!
//! This module contains simple examples demonstrating various Rust concepts:
//! - Constants and statics
//! - Functions and closures
//! - Ownership and borrowing with Cow
//! - Control flow

use std::borrow::Cow;

/// Threshold constant for "big" number classification
pub const THRESHOLD: i32 = 100;

/// Checks if a number is considered "big" (greater than threshold)
///
/// # Examples
///
/// ```
/// use rlab::examples::is_big;
///
/// assert!(!is_big(50));
/// assert!(!is_big(100));
/// assert!(is_big(101));
/// ```
pub fn is_big(n: i32) -> bool {
    n > THRESHOLD
}

/// Applies a closure to execute some action
///
/// Demonstrates higher-order functions and FnOnce trait bounds.
///
/// # Examples
///
/// ```
/// use rlab::examples::apply;
///
/// let mut result = 0;
/// apply(|| {
///     result = 42;
/// });
/// assert_eq!(result, 42);
/// ```
pub fn apply<F>(f: F)
where
    F: FnOnce(),
{
    f();
}

/// Converts all negative values in a slice to their absolute values
///
/// Demonstrates `Cow` (Clone on Write) for efficient conditional mutation.
/// The slice is only cloned if mutation is actually needed.
///
/// # Examples
///
/// ```
/// use std::borrow::Cow;
/// use rlab::examples::abs_all;
///
/// // No clone occurs - all values are non-negative
/// let slice = [0, 1, 2];
/// let mut input = Cow::from(&slice[..]);
/// abs_all(&mut input);
///
/// // Clone occurs because mutation is needed
/// let slice = [-1, 0, 1];
/// let mut input = Cow::from(&slice[..]);
/// abs_all(&mut input);
/// assert_eq!(input.as_ref(), &[1, 0, 1]);
/// ```
pub fn abs_all(input: &mut Cow<'_, [i32]>) {
    for i in 0..input.len() {
        let v = input[i];
        if v < 0 {
            // to_mut() clones into a Vec only if not already owned
            input.to_mut()[i] = -v;
        }
    }
}

/// Creates a closure that adds one to its input plus a captured value
///
/// Demonstrates closure capture and the move keyword.
///
/// # Examples
///
/// ```
/// use rlab::examples::make_adder;
///
/// let add_five = make_adder(5);
/// assert_eq!(add_five(10), 16); // 10 + 1 + 5 = 16
/// ```
pub fn make_adder(n: i32) -> impl Fn(i32) -> i32 {
    move |x| x + 1 + n
}

/// Runs all basic examples, printing results to stdout
///
/// This function is useful for interactive exploration of the examples.
pub fn run_examples() {
    println!("=== Basic Rust Examples ===\n");
    
    // Example 1: Constant and is_big
    let n = 1000;
    println!("{} is {}", n, if is_big(n) { "big" } else { "small" });
    
    // Example 2: Closure with environment capture
    let add_one = make_adder(0); // effectively adds 1
    println!("add_one(1): {}", add_one(1));
    
    // Example 3: Higher-order function
    apply(|| println!("Hello from a closure!"));
    
    // Example 4: Cow - no clone needed
    println!("\n-- Cow Examples --");
    let slice = [0, 1, 2];
    let mut input = Cow::from(&slice[..]);
    println!("Before abs_all (all positive): {:?}", input);
    abs_all(&mut input);
    println!("After: {:?}, is_owned: {}\n", input, matches!(input, Cow::Owned(_)));
    
    // Example 5: Cow - clone occurs
    let slice = [-1, 0, 1];
    let mut input = Cow::from(&slice[..]);
    println!("Before abs_all (has negative): {:?}", input);
    abs_all(&mut input);
    println!("After: {:?}, is_owned: {}\n", input, matches!(input, Cow::Owned(_)));
    
    // Example 6: Cow - already owned
    let mut input = Cow::from(vec![-1, 0, 1]);
    println!("Before abs_all (already owned): {:?}", input);
    abs_all(&mut input);
    println!("After: {:?}, is_owned: {}\n", input, matches!(input, Cow::Owned(_)));
    
    println!("=== Examples Complete ===");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_is_big() {
        assert!(!is_big(0));
        assert!(!is_big(100));
        assert!(is_big(101));
        assert!(is_big(1000));
    }

    #[test]
    fn test_apply() {
        let mut called = false;
        apply(|| {
            called = true;
        });
        assert!(called);
    }

    #[test]
    fn test_abs_all_borrowed_no_clone() {
        let slice = [0, 1, 2];
        let mut input = Cow::from(&slice[..]);
        abs_all(&mut input);
        assert!(matches!(input, Cow::Borrowed(_)));
        assert_eq!(input.as_ref(), &[0, 1, 2]);
    }

    #[test]
    fn test_abs_all_borrowed_with_clone() {
        let slice = [-1, 0, 1];
        let mut input = Cow::from(&slice[..]);
        abs_all(&mut input);
        assert!(matches!(input, Cow::Owned(_)));
        assert_eq!(input.as_ref(), &[1, 0, 1]);
    }

    #[test]
    fn test_abs_all_owned() {
        let mut input = Cow::from(vec![-1, 0, 1]);
        abs_all(&mut input);
        assert!(matches!(input, Cow::Owned(_)));
        assert_eq!(input.as_ref(), &[1, 0, 1]);
    }

    #[test]
    fn test_make_adder() {
        let add_five = make_adder(5);
        assert_eq!(add_five(0), 6);
        assert_eq!(add_five(10), 16);
        
        let add_ten = make_adder(10);
        assert_eq!(add_ten(5), 16);
    }
}
