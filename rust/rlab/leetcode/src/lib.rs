//! LeetCode Problem Solutions
//!
//! This crate contains solutions to LeetCode problems, organized by problem number.
//! Each module corresponds to a specific problem or category of problems.
//!
//! ## Structure
//!
//! - `array/` - Array and string problems
//! - `linked_list/` - Linked list problems
//! - `tree/` - Tree and graph problems
//! - `dp/` - Dynamic programming problems
//! - `sorting/` - Sorting and searching problems
//! - `misc/` - Miscellaneous problems

#![warn(missing_docs)]
#![allow(dead_code)]

#[macro_use]
pub mod util;

pub mod problem;
pub mod solution;

pub mod array;
pub mod dp;
pub mod linked_list;
pub mod misc;
pub mod sorting;
pub mod tree;

/// Utility function to run tests for a specific problem
#[cfg(test)]
pub mod utils {
    /// Helper to assert two vectors are equal (ignoring order if needed)
    pub fn assert_vec_eq<T: PartialEq + std::fmt::Debug>(a: &[T], b: &[T]) {
        assert_eq!(
            a, b,
            "Vectors are not equal:\n  left: {:?}\n right: {:?}",
            a, b
        );
    }

    /// Helper to assert two 2D vectors are equal
    pub fn assert_vec2d_eq<T: PartialEq + std::fmt::Debug + Clone>(
        mut a: Vec<Vec<T>>,
        mut b: Vec<Vec<T>>,
    ) {
        // Sort inner vectors for comparison
        for v in &mut a {
            v.sort_by(|x, y| format!("{:?}", x).cmp(&format!("{:?}", y)));
        }
        for v in &mut b {
            v.sort_by(|x, y| format!("{:?}", x).cmp(&format!("{:?}", y)));
        }
        // Sort outer vectors
        a.sort_by(|x, y| format!("{:?}", x).cmp(&format!("{:?}", y)));
        b.sort_by(|x, y| format!("{:?}", x).cmp(&format!("{:?}", y)));

        assert_eq!(a, b);
    }
}
