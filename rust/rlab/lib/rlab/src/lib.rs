//! rlab - Rust Learning and Algorithms Library
//!
//! A collection of algorithms, data structures, and utilities for learning Rust.
//!
//! # Modules
//!
//! - [`common`] - Common utilities and algorithms
//! - [`sort`] - Sorting algorithms collection
//!
//! # Examples
//!
//! ```
//! use rlab::add;
//!
//! assert_eq!(add(2, 2), 4);
//! ```

#![warn(missing_docs)]
#![warn(rust_2018_idioms)]

pub mod common;

/// Re-export sort module for convenience
pub use common::sort;

/// Adds two unsigned integers together.
///
/// This is a simple example function demonstrating documentation and testing.
///
/// # Examples
///
/// Basic usage:
///
/// ```
/// use rlab::add;
///
/// assert_eq!(add(2, 2), 4);
/// assert_eq!(add(0, 0), 0);
/// assert_eq!(add(usize::MAX, 0), usize::MAX);
/// ```
///
/// # Overflow Behavior
///
/// This function will panic in debug mode on overflow:
///
/// ```should_panic
/// use rlab::add;
/// let _ = add(usize::MAX, 1); // panics!
/// ```
///
/// In release mode, it will wrap around (two's complement).
pub fn add(left: usize, right: usize) -> usize {
    left + right
}

/// Calculates the factorial of a non-negative integer.
///
/// # Examples
///
/// ```
/// use rlab::factorial;
///
/// assert_eq!(factorial(0), 1);
/// assert_eq!(factorial(1), 1);
/// assert_eq!(factorial(5), 120);
/// ```
///
/// # Panics
///
/// This function currently uses recursion and may cause a stack overflow
/// for very large inputs. A future version should use iteration instead.
pub fn factorial(n: u64) -> u64 {
    match n {
        0 | 1 => 1,
        _ => n * factorial(n - 1),
    }
}

/// Finds the greatest common divisor using Euclid's algorithm.
///
/// # Examples
///
/// ```
/// use rlab::gcd;
///
/// assert_eq!(gcd(48, 18), 6);
/// assert_eq!(gcd(56, 98), 14);
/// assert_eq!(gcd(101, 10), 1);
/// ```
pub fn gcd(mut a: u64, mut b: u64) -> u64 {
    while b != 0 {
        let temp = b;
        b = a % b;
        a = temp;
    }
    a
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_add() {
        assert_eq!(add(2, 2), 4);
        assert_eq!(add(0, 0), 0);
        assert_eq!(add(100, 200), 300);
    }

    #[test]
    fn test_factorial() {
        assert_eq!(factorial(0), 1);
        assert_eq!(factorial(1), 1);
        assert_eq!(factorial(5), 120);
        assert_eq!(factorial(10), 3_628_800);
    }

    #[test]
    fn test_gcd() {
        assert_eq!(gcd(48, 18), 6);
        assert_eq!(gcd(18, 48), 6);
        assert_eq!(gcd(101, 10), 1);
        assert_eq!(gcd(0, 5), 5);
        assert_eq!(gcd(5, 0), 5);
    }
}
