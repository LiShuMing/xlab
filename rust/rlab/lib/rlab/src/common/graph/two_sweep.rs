//! The two-sweep (double DFS) method for the tree diameter.
//!
//! # Algorithm
//!
//! 1. DFS from an arbitrary node `s`, keep the node `a` farthest from it.
//! 2. DFS from `a`, keep the node `b` farthest from it. `dist(a, b)` is the
//!    diameter.
//!
//! The full proof is in [`crate::common::graph::tree_dp`]'s module
//! documentation. Step 1 is the only subtle half: it shows that for any
//! diameter `(u, v)` and any `x` on it, some endpoint of `(u, v)` is at
//! distance at least the diameter from `a`, which forces that distance to equal
//! the diameter and makes `a` an endpoint too.
//!
//! # Precondition: no negative edge weights
//!
//! Both sweeps assume distances are monotone along a walk, which fails the
//! moment an edge is negative: the farthest *simple* path need not be the one
//! the traversal picks, because a sweep commits to the single rooted path that
//! looks best at the moment it reaches a node and never reconsiders. The
//! `negative_weight_breaks_the_precondition` test in this file carries a
//! concrete six-node tree where the sweeps answer `4` and the true diameter is
//! `5`, so [`tree_diameter`] is only meaningful when
//! [`Tree::has_non_negative_weights`] holds; use
//! [`crate::common::graph::tree_dp::tree_diameter`] for negative weights.
//!
//! # Cost
//!
//! Two linear scans: `O(n)` time, `O(n)` auxiliary space for the DFS stack and
//! the distance/parent arrays. The recursion is a plain array-backed stack, so
//! a path graph of a million nodes cannot overflow the call stack.
//!
//! # Choosing between the two implementations
//!
//! | Condition | Use |
//! | --- | --- |
//! | Tree is unweighted, or weights are non-negative | [`tree_diameter`] |
//! | Some edge weights are negative | [`crate::common::graph::tree_dp::tree_diameter`] |
//! | You need the actual path, not just its length | [`tree_diameter_path`] |
//!
//! # Examples
//!
//! ```
//! use rlab::common::graph::{tree_diameter, Tree};
//!
//! // 0 -- 1 -- 2 -- 3
//! let tree = Tree::from_children(&[vec![1], vec![2], vec![3], vec![]]);
//! assert_eq!(tree_diameter(&tree), 3);
//! ```

use super::tree::Tree;

/// Length of the longest path in `tree`, using two distance sweeps.
///
/// Only correct when no edge weight is negative; see the module documentation.
///
/// # Examples
///
/// ```
/// use rlab::common::graph::{tree_diameter, Tree};
///
/// // A star: every path is at most two edges long.
/// let star = Tree::from_children(&[vec![1, 2, 3], vec![], vec![], vec![]]);
/// assert_eq!(tree_diameter(&star), 2);
/// ```
#[must_use]
pub fn tree_diameter(tree: &Tree) -> i64 {
    // Sweep 1: any node works as a starting point.
    let (a, _) = farthest_from(tree, 0);
    // Sweep 2: the farthest node from `a` closes a diameter.
    let (_, diameter) = farthest_from(tree, a);
    diameter
}

/// Length of the longest path in `tree` together with the nodes along it.
///
/// The path is simple (no repeated node) and ordered from `a`, the node the
/// first sweep selected, to `b`, the node the second sweep selected. Both are
/// diameter endpoints, so the result reads end-to-end; which physical endpoint
/// lands first depends on where node `0` sits. As with [`tree_diameter`],
/// negative edge weights are out of scope.
///
/// # Examples
///
/// ```
/// use rlab::common::graph::{tree_diameter_path, Tree};
///
/// // 0 -- 1 -- 2 -- 3, so the first sweep from 0 selects node 3.
/// let tree = Tree::from_children(&[vec![1], vec![2], vec![3], vec![]]);
/// let (length, path) = tree_diameter_path(&tree);
/// assert_eq!(length, 3);
/// assert_eq!(path, vec![3, 2, 1, 0]);
/// ```
#[must_use]
pub fn tree_diameter_path(tree: &Tree) -> (i64, Vec<usize>) {
    let (a, _) = farthest_from(tree, 0);
    let (dist, parent) = sweep(tree, a);
    let b = argmax(&dist).expect("a tree always has at least one node");

    // Walk the predecessor chain from `b` back to the root `a`.
    let mut path = vec![b];
    let mut v = b;
    while v != a {
        v = parent[v];
        path.push(v);
    }
    path.reverse();
    (dist[b], path)
}

/// One DFS from `start`, returning per-node distance and the DFS parent array.
///
/// The parent of `start` is itself, which doubles as the "no parent" marker
/// because the traversal never revisits the node it came from.
fn sweep(tree: &Tree, start: usize) -> (Vec<i64>, Vec<usize>) {
    let n = tree.node_count();
    let mut dist = vec![0i64; n];
    let mut parent = vec![start; n];
    let mut visited = vec![false; n];

    visited[start] = true;
    let mut stack = vec![start];
    while let Some(v) = stack.pop() {
        for (to, w) in tree.neighbors(v) {
            if !visited[to] {
                visited[to] = true;
                parent[to] = v;
                dist[to] = dist[v] + w;
                stack.push(to);
            }
        }
    }

    (dist, parent)
}

/// Farthest node from `start` and its distance.
///
/// Ties are broken towards the smaller label so the result is deterministic.
fn farthest_from(tree: &Tree, start: usize) -> (usize, i64) {
    let (dist, _) = sweep(tree, start);
    argmax(&dist).map_or((start, 0), |v| (v, dist[v]))
}

/// Index of the largest entry, preferring the smallest index on ties.
fn argmax(values: &[i64]) -> Option<usize> {
    values.iter().enumerate().max_by_key(|&(i, &d)| (d, std::cmp::Reverse(i))).map(|(i, _)| i)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn single_node_has_zero_diameter() {
        let tree = Tree::from_children(&[vec![]]);
        assert_eq!(tree_diameter(&tree), 0);
        assert_eq!(tree_diameter_path(&tree), (0, vec![0]));
    }

    #[test]
    fn path_graph_diameter_is_the_whole_path() {
        let tree = Tree::from_children(&[vec![1], vec![2], vec![3], vec![]]);
        assert_eq!(tree_diameter(&tree), 3);
        // Sweep 1 already reaches the far end of the line, so the path runs
        // from node 3 back to node 0.
        assert_eq!(tree_diameter_path(&tree), (3, vec![3, 2, 1, 0]));
    }

    #[test]
    fn star_diameter_does_not_pass_through_the_hub() {
        let star = Tree::from_children(&[vec![1, 2, 3], vec![], vec![], vec![]]);
        assert_eq!(tree_diameter(&star), 2);
        assert_eq!(tree_diameter_path(&star), (2, vec![1, 0, 2]));
    }

    #[test]
    fn weighted_tree_uses_edge_weights() {
        // Long in edge count but short in weight: 0 -1- 1 -1- 2 -1- 3
        // Shorter in edge count but heavy:       0 -10- 4
        let tree =
            Tree::from_weighted_edges(5, &[(0, 1, 1), (1, 2, 1), (2, 3, 1), (0, 4, 10)]);
        // 3 -> 2 -> 1 -> 0 -> 4 has length 1 + 1 + 1 + 10 = 13, which beats
        // both the three-edge chain (3) and the direct heavy edge (10).
        assert_eq!(tree_diameter(&tree), 13);
        let (length, path) = tree_diameter_path(&tree);
        assert_eq!(length, 13);
        assert_eq!(path, vec![4, 0, 1, 2, 3]);
    }

    #[test]
    fn an_endpoint_reached_from_zero_is_still_an_endpoint() {
        //         0
        //        / \
        //       1   4
        //       |
        //       2
        //       |
        //       3
        // Sweeping from node 0 lands on node 3, and 3 -> 4 spans four edges.
        let tree = Tree::from_children(&[vec![1, 4], vec![2], vec![3], vec![], vec![]]);
        let (a, _) = farthest_from(&tree, 0);
        assert_eq!(a, 3);
        assert_eq!(tree_diameter(&tree), 4);
        assert_eq!(tree_diameter_path(&tree), (4, vec![3, 2, 1, 0, 4]));
    }

    #[test]
    fn negative_weight_breaks_the_precondition() {
        //          1
        //          | 2
        //          0
        //          | -1          true diameter: 5 -- 2 -- 3, length 3 + 2 = 5
        //          2
        //       2 / \ 3
        //        3   5
        //        | -1
        //        4
        let tree = Tree::from_weighted_edges(
            6,
            &[(0, 1, 2), (0, 2, -1), (2, 3, 2), (2, 5, 3), (3, 4, -1)],
        );
        assert!(!tree.has_non_negative_weights());

        // Sweep 1 from 0: nodes 1 and 5 tie at distance 2, so the tie-break
        // picks node 1. Sweep 2 from 1: node 5 is farthest at distance 4.
        // The algorithm answers 4 and never sees the longer 5 -- 2 -- 3 path.
        assert_eq!(
            tree_diameter(&tree),
            4,
            "two-sweep misses the path 5 -- 2 -- 3"
        );

        // The tree-DP variant is the one that stays correct here.
        assert_eq!(super::super::tree_dp::tree_diameter(&tree), 5);
    }

    #[test]
    fn deep_chain_does_not_overflow_the_stack() {
        // 200k nodes in a line: an explicitly stacked DFS must survive where a
        // naive recursive one would blow the call stack.
        let n = 200_000;
        let mut children = vec![Vec::new(); n];
        for v in 0..n - 1 {
            children[v].push(v + 1);
        }
        let tree = Tree::from_children(&children);
        assert_eq!(tree_diameter(&tree), (n - 1) as i64);
    }
}
