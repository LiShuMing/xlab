//! Shared tree representation for the diameter algorithms.
//!
//! Both [`crate::common::graph::two_sweep`] and
//! [`crate::common::graph::tree_dp`] run over the same compressed adjacency
//! structure, so the two algorithms differ only in the traversal, never in how
//! the input is read or in how the recursion is made iterative.
//!
//! Weights are signed. That looks like overkill for an unweighted tree, but it
//! is deliberate: the two-sweep algorithm is only correct when no weight is
//! negative, while the tree-DP algorithm is correct either way. Keeping the
//! weight type signed lets that difference be stated in the types and exercised
//! by a test rather than asserted in prose.

/// A rooted tree with `n` nodes labelled `0..n`, stored in CSR form.
///
/// Node `0` is the root. The adjacency is symmetric: for every logical edge
/// `(u, v, w)` both `(v, w)` appears in `u`'s slice and `(u, w)` in `v`'s.
/// A traversal started at the root therefore skips the single neighbour that
/// equals the current node's parent.
///
/// # Examples
///
/// ```
/// use rlab::common::graph::Tree;
///
/// // 0 -- 1 -- 2
/// let tree = Tree::from_children(&[vec![1], vec![2], vec![]]);
/// assert_eq!(tree.node_count(), 3);
/// assert_eq!(tree.neighbors(1).count(), 2);
/// ```
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Tree {
    /// `head[v]..head[v + 1]` is the slice of `adj` holding `v`'s neighbours.
    head: Vec<usize>,
    /// `(neighbour, edge weight)` pairs, grouped by the node that owns them.
    adj: Vec<(usize, i64)>,
}

impl Tree {
    /// Number of nodes in the tree.
    #[must_use]
    pub fn node_count(&self) -> usize {
        self.head.len() - 1
    }

    /// The neighbours of `v` together with the weights of the connecting edges.
    #[must_use = "iterators are lazy and do nothing unless consumed"]
    pub fn neighbors(&self, v: usize) -> impl Iterator<Item = (usize, i64)> + '_ {
        self.adj[self.head[v]..self.head[v + 1]].iter().copied()
    }

    /// `true` when every edge weight is non-negative.
    ///
    /// This is the precondition of [`crate::common::graph::tree_diameter`]; the
    /// tree-DP variant does not need it.
    #[must_use]
    pub fn has_non_negative_weights(&self) -> bool {
        self.adj.iter().all(|&(_, w)| w >= 0)
    }

    /// Builds an unweighted tree from a parent-indexed child list.
    ///
    /// `children[v]` lists the nodes whose parent is `v`; every implied edge
    /// has weight `1`. The outer slice must have exactly one entry per node and
    /// node `0` is the root.
    ///
    /// # Panics
    ///
    /// Panics if the child lists reference a node outside `0..children.len()`.
    #[must_use]
    pub fn from_children(children: &[Vec<usize>]) -> Tree {
        let mut edges = Vec::new();
        for (v, list) in children.iter().enumerate() {
            for &child in list {
                edges.push((v, child, 1i64));
            }
        }
        Tree::from_weighted_edges(children.len(), &edges)
    }

    /// Builds a weighted tree from an arbitrary edge list.
    ///
    /// The edges are treated as an undirected tree; the caller is responsible
    /// for supplying a connected, acyclic graph of `n - 1` edges.
    ///
    /// # Panics
    ///
    /// Panics if `n` is zero or if an endpoint is outside `0..n`.
    #[must_use]
    pub fn from_weighted_edges(n: usize, edges: &[(usize, usize, i64)]) -> Tree {
        assert!(n > 0, "a tree needs at least one node");

        let mut degree = vec![0usize; n];
        for &(u, v, _) in edges {
            assert!(u < n && v < n, "edge endpoint out of range");
            degree[u] += 1;
            degree[v] += 1;
        }

        let mut head = vec![0usize; n + 1];
        for v in 0..n {
            head[v + 1] = head[v] + degree[v];
        }

        let mut adj = vec![(0usize, 0i64); head[n]];
        let mut cursor = head.clone();
        for &(u, v, w) in edges {
            adj[cursor[u]] = (v, w);
            cursor[u] += 1;
            adj[cursor[v]] = (u, w);
            cursor[v] += 1;
        }

        Tree { head, adj }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn from_children_is_symmetric() {
        //        0
        //       / \
        //      1   2
        //     /
        //    3
        let tree = Tree::from_children(&[vec![1, 2], vec![3], vec![], vec![]]);
        assert_eq!(tree.node_count(), 4);
        assert_eq!(tree.neighbors(0).count(), 2);
        assert_eq!(tree.neighbors(1).count(), 2);
        assert_eq!(tree.neighbors(3).count(), 1);

        let mut from_zero = tree.neighbors(0);
        assert_eq!(from_zero.next(), Some((1, 1)));
        assert_eq!(from_zero.next(), Some((2, 1)));
        assert_eq!(from_zero.next(), None);

        // Every edge shows up in both directions.
        for v in 0..tree.node_count() {
            for (to, w) in tree.neighbors(v) {
                assert!(tree.neighbors(to).any(|(back, back_w)| back == v && back_w == w));
            }
        }
    }

    #[test]
    fn single_node_has_no_neighbours() {
        let tree = Tree::from_children(&[vec![]]);
        assert_eq!(tree.node_count(), 1);
        assert_eq!(tree.neighbors(0).count(), 0);
    }

    #[test]
    fn weighted_edges_preserve_weights() {
        let tree = Tree::from_weighted_edges(3, &[(0, 1, 7), (1, 2, 4)]);
        assert_eq!(tree.neighbors(1).collect::<Vec<_>>(), vec![(0, 7), (2, 4)]);
    }

    #[test]
    fn negative_weights_are_reported() {
        let tree = Tree::from_weighted_edges(2, &[(0, 1, -3)]);
        assert!(!tree.has_non_negative_weights());
        assert!(Tree::from_children(&[vec![1], vec![]]).has_non_negative_weights());
    }

    #[test]
    #[should_panic(expected = "at least one node")]
    fn empty_tree_is_rejected() {
        let _ = Tree::from_children(&[]);
    }
}
