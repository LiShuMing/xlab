//! Tree algorithms
//!
//! This module currently covers the **diameter** of a tree — the weight of its
//! longest simple path — implemented two ways so the trade-off between them can
//! be read side by side.
//!
//! # The two methods
//!
//! - [`two_sweep`] — the double-DFS method. Two linear scans from an arbitrary
//!   node and then from the farthest node found. This is the cheaper one to
//!   reach for because it is shortest, and [`two_sweep::tree_diameter_path`]
//!   additionally hands back the path itself. Its price is a precondition:
//!   every edge weight must be non-negative.
//! - [`tree_dp`] — the bottom-up method. One post-order pass that keeps, for
//!   each node, the best downward path in its subtree. A little more code and
//!   `O(n)` more memory than the sweep, but correct for arbitrary weights.
//!
//! The correctness argument for both lives in [`tree_dp`]'s module
//! documentation.
//!
//! # Which one to use
//!
//! | Situation | Choice |
//! | --- | --- |
//! | Unweighted tree, any size | [`two_sweep::tree_diameter`] |
//! | Weighted tree, all weights `>= 0` | [`two_sweep::tree_diameter`] — faster constant factor |
//! | Weighted tree, negative weights possible | [`tree_dp::tree_diameter`] |
//! | You need the diameter *path* | [`two_sweep::tree_diameter_path`] |
//! | You need an answer per subtree, or a count of diameters | [`tree_dp::tree_diameter`] |
//!
//! Both run in `O(n)` time and `O(n)` space, and neither recurses: the DFS is
//! an explicit `Vec` stack, so a path graph of a million nodes does not blow the
//! call stack.
//!
//! # Rooting convention
//!
//! [`Tree`] always roots at node `0`. Every algorithm below is independent of
//! where the root sits, so this choice only affects the traversal order and the
//! tie-breaking in [`two_sweep`].
//!
//! # Examples
//!
//! ```
//! use rlab::common::graph::{tree_diameter, tree_dp, Tree};
//!
//! // 0 -- 1 -- 2 -- 3, unweighted.
//! let tree = Tree::from_children(&[vec![1], vec![2], vec![3], vec![]]);
//! assert_eq!(tree_diameter(&tree), 3);
//! assert_eq!(tree_dp::tree_diameter(&tree), 3);
//!
//! // Weighted, still non-negative: the sweeps agree with the DP.
//! let weighted =
//!     Tree::from_weighted_edges(5, &[(0, 1, 1), (1, 2, 1), (2, 3, 1), (0, 4, 10)]);
//! assert_eq!(tree_diameter(&weighted), 13);
//! assert_eq!(tree_dp::tree_diameter(&weighted), 13);
//! ```

pub mod tree;
pub mod tree_dp;
pub mod two_sweep;

pub use tree::Tree;
pub use two_sweep::{tree_diameter, tree_diameter_path};
