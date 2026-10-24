//! The tree-DP (bottom-up) method for the tree diameter, and the proofs for
//! both methods.
//!
//! # Algorithm
//!
//! Root the tree anywhere. For each node `v` let `down(v)` be the largest
//! weight of a downward path that starts at `v` and descends into `v`'s
//! subtree, the empty path included:
//!
//! ```text
//! down(v) = max(0, max over children c of ( w(v, c) + down(c) ))
//! ```
//!
//! Every simple path has a unique *highest* node, the one closest to the root.
//! If that node is `v` and the path is non-empty, the path is the concatenation
//! of two downward paths rooted at `v` through two **distinct** children, so
//!
//! ```text
//! best(v) = top1(v) + top2(v)
//! ```
//!
//! where `top1`, `top2` are the two largest values of `w(v, c) + down(c)`.
//! Different children guarantee the concatenation is simple; taking the two
//! largest guarantees it is the best such path. The diameter is the largest
//! `best(v)` over all `v` (equivalently, `top1(v) + top2(v)` is the diameter of
//! the subgraph hanging off `v`).
//!
//! Two deliberate details:
//!
//! - The empty path is allowed (`down(v) >= 0`), so a one-ended path — one that
//!   runs from `v` down to a single descendant — is covered by the `top2 = 0`
//!   case. Without this, a path graph would report one edge too few.
//! - Using the two *best* children rather than requiring a path to *use* `v`
//!   means the maximum over all descendants already contains every path whose
//!   highest node is below `v`; that is the role of the running maximum.
//!
//! # Cost
//!
//! One post-order pass: `O(n)` time and `O(n)` space for the parent/order
//! arrays, `order` and `down`. The post-order is built by an explicit stack
//! rather than recursion.
//!
//! # Proof that the tree-DP algorithm is correct
//!
//! **Invariant.** After the post-order pass, `down(v)` equals the maximum
//! weight of a path that begins at `v` and stays inside `v`'s subtree. The
//! empty path has weight `0` and is always available, so `down(v) >= 0`, and
//! any non-empty such path leaves `v` through exactly one child `c` and then
//! continues inside `c`'s subtree, contributing `w(v, c) + down(c)` by the
//! induction hypothesis. The recurrence therefore enumerates every candidate
//! exactly once, and returns the largest. Induction on subtree height gives the
//! invariant for all `v`.
//!
//! **Coverage.** Let `P` be any simple path and let `v` be its highest node.
//! Split `P` at `v`: either `P` is empty, or `P` is `P1` then `P2`, where `P1`
//! and `P2` descend from `v` through two distinct children (they are distinct
//! because `P` is simple and both start at `v`). Each `Pi` is a downward path
//! from `v`, so `weight(Pi) <= top1(v)`, and since the two children differ, the
//! two values `w(v, c1) + down(c1)` and `w(v, c2) + down(c2)` are distinct
//! entries in `v`'s candidate list. Hence `weight(P) = weight(P1) + weight(P2)
//! <= top1(v) + top2(v) = best(v)`. The maximum of `best` over all nodes is
//! therefore at least the diameter.
//!
//! **Soundness.** Conversely, each `best(v)` is the weight of a genuine simple
//! path: choose the two children attaining `top1(v)` and `top2(v)`, take the
//! best downward path in each, and join them at `v`. The joined walk is simple
//! because the two downward paths live in disjoint subtrees; an empty arm
//! degenerates to a one-ended path, still simple. So every `best(v)` is
//! achievable, and the maximum of `best` is at most the diameter.
//!
//! Both inequalities give equality. `0` is returned for a single node, matching
//! the empty path being a legal (zero-length) answer. ∎
//!
//! # Proof that the two-sweep algorithm is correct
//!
//! Throughout, `d(p, q)` is the weight of the unique `p`-to-`q` path, `D` is
//! the diameter, and all weights are assumed non-negative; see
//! [`crate::common::graph::two_sweep`] for what fails without that.
//!
//! Two tree facts are used repeatedly. Every three vertices `p, q, r` have a
//! unique **median** `med(p, q, r)`, the vertex common to the paths `p`-`q`,
//! `q`-`r` and `r`-`p`; it satisfies `d(p, q) = d(p, m) + d(m, q)` and likewise
//! for the other two pairs. And every vertex has a unique **projection** onto a
//! path, the closest vertex of that path.
//!
//! **Step 1 — the first sweep lands on a diameter endpoint.** Let `s` be the
//! start, `a` a vertex farthest from `s`, and `(u, v)` a diameter, so
//! `d(u, v) = D`. Let `x = med(s, u, v)`. Then `x` lies on the `u`-`v` path,
//! giving
//!
//! ```text
//! d(s, u) = d(s, x) + d(x, u),   d(s, v) = d(s, x) + d(x, v),
//! D = d(x, u) + d(x, v).
//! ```
//!
//! Swap `u` and `v` if necessary so that `d(x, u) <= d(x, v)`. Let
//! `y = med(s, a, v)`. Both `x` and `y` lie on the path `s`-`v`, so `y` lies
//! either on `s`-`x` or on `x`-`v`; these are the only two cases.
//!
//! *Case `y` on `s`-`x`.* Then `d(y, v) = d(y, x) + d(x, v) >= d(x, v)`,
//! because `d(y, x) >= 0` — this is the one place non-negativity is needed.
//! Since `y` is the median of `s, a, v`, `d(s, a) = d(s, y) + d(y, a)` and
//! `d(s, v) = d(s, y) + d(y, v)`; as `a` is farthest from `s`,
//! `d(y, a) >= d(y, v)`. And `y` lies on the `a`-`v` path, so
//!
//! ```text
//! d(a, v) = d(a, y) + d(y, v) >= 2 * d(y, v) >= d(x, v) + d(x, u) = D,
//! ```
//!
//! the middle step using `d(y, v) >= d(x, v) >= d(x, u)`.
//!
//! *Case `y` on `x`-`v`.* Then `y` also lies on the `u`-`v` path, so `y` is the
//! projection of `a` onto that path and `d(a, u) = d(a, y) + d(y, u)`. As `y`
//! lies between `x` and `v`, `d(y, u) = d(x, u) + d(x, y)` and
//! `d(y, v) = d(x, v) - d(x, y)`. Farthest-ness of `a` again gives
//! `d(s, a) >= d(s, v)`, and `d(s, a) = d(s, x) + d(x, y) + d(a, y)`, so
//! `d(a, y) + d(x, y) >= d(x, v)`. Therefore
//!
//! ```text
//! d(a, u) = d(a, y) + d(y, u) = d(a, y) + d(x, y) + d(x, u) >= d(x, v) + d(x, u) = D.
//! ```
//!
//! Either way some endpoint of `(u, v)` is at distance `>= D` from `a`; since
//! `D` is the diameter, that distance equals `D`, so `a` is an endpoint of a
//! diameter. ∎
//!
//! **Step 2 — the second sweep measures the diameter.** The second sweep starts
//! at `a`, a diameter endpoint by step 1, and returns `b`, farthest from `a`.
//! Let `(a, u')` be a diameter with endpoint `a`. Since `b` is farthest from
//! `a`, `d(a, b) >= d(a, u') = D`; and `d(a, b) <= D` because no path exceeds
//! the diameter. Hence `d(a, b) = D`, and the sweep reports exactly the
//! diameter. ∎
//!
//! # Choosing between the two implementations
//!
//! | Condition | Use |
//! | --- | --- |
//! | Unweighted tree, or non-negative weights | Either; two-sweep also gives the path |
//! | Negative weights | [`tree_diameter`] |
//! | Need per-subtree answers or a count of diameters | [`tree_diameter`] |
//!
//! # Examples
//!
//! ```
//! use rlab::common::graph::{tree_dp::tree_diameter, Tree};
//!
//! // 0 -- 1 -- 2 -- 3
//! let tree = Tree::from_children(&[vec![1], vec![2], vec![3], vec![]]);
//! assert_eq!(tree_diameter(&tree), 3);
//! ```

use super::tree::Tree;

/// Length of the longest path in `tree`.
///
/// Correct for arbitrary (including negative) edge weights, at the cost of
/// `O(n)` extra storage for the post-order arrays.
///
/// # Examples
///
/// ```
/// use rlab::common::graph::{tree_dp::tree_diameter, Tree};
///
/// //        0
/// //       / \
/// //      1   2
/// //     / \
/// //    3   4
/// let tree = Tree::from_children(&[vec![1, 2], vec![3, 4], vec![], vec![], vec![]]);
/// assert_eq!(tree_diameter(&tree), 3);
/// ```
#[must_use]
pub fn tree_diameter(tree: &Tree) -> i64 {
    let (parent, order) = post_order(tree);
    let mut down = vec![0i64; tree.node_count()];
    let mut diameter = 0;

    // `order` is a pre-order with parents before children, so walking it in
    // reverse visits every node after all of its descendants.
    for &v in order.iter().rev() {
        let mut top1 = 0;
        let mut top2 = 0;
        for (child, weight) in tree.neighbors(v) {
            if child == parent[v] {
                continue;
            }
            let candidate = weight + down[child];
            if candidate > top1 {
                top2 = top1;
                top1 = candidate;
            } else if candidate > top2 {
                top2 = candidate;
            }
        }
        down[v] = top1;
        diameter = diameter.max(top1 + top2);
    }

    diameter
}

/// Rooted parent array plus a parent-before-child traversal order.
///
/// The traversal is an explicit stack, so a path graph cannot overflow the
/// call stack. The parent of the root is `usize::MAX`, which no neighbour can
/// equal.
fn post_order(tree: &Tree) -> (Vec<usize>, Vec<usize>) {
    let n = tree.node_count();
    let mut parent = vec![usize::MAX; n];
    let mut visited = vec![false; n];
    let mut order = Vec::with_capacity(n);

    visited[0] = true;
    let mut stack = vec![0];
    while let Some(v) = stack.pop() {
        order.push(v);
        for (to, _) in tree.neighbors(v) {
            if !visited[to] {
                visited[to] = true;
                parent[to] = v;
                stack.push(to);
            }
        }
    }

    (parent, order)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Reference implementation: walk every simple path and keep the longest.
    /// Only usable on tiny trees, so it backs the randomized cross-check.
    ///
    /// `best` starts at `0` because the empty path is a legal answer, matching
    /// [`tree_diameter`]'s convention.
    fn brute_force(tree: &Tree) -> i64 {
        let n = tree.node_count();
        let mut best = 0;
        for start in 0..n {
            let mut stack = vec![(start, usize::MAX, 0i64)];
            while let Some((v, from, d)) = stack.pop() {
                best = best.max(d);
                for (to, w) in tree.neighbors(v) {
                    if to != from {
                        stack.push((to, v, d + w));
                    }
                }
            }
        }
        best
    }

    #[test]
    fn single_node_has_zero_diameter() {
        let tree = Tree::from_children(&[vec![]]);
        assert_eq!(tree_diameter(&tree), 0);
    }

    #[test]
    fn path_graph_diameter_is_the_whole_path() {
        let tree = Tree::from_children(&[vec![1], vec![2], vec![3], vec![]]);
        assert_eq!(tree_diameter(&tree), 3);
    }

    #[test]
    fn star_diameter_does_not_pass_through_the_hub() {
        let star = Tree::from_children(&[vec![1, 2, 3], vec![], vec![], vec![]]);
        assert_eq!(tree_diameter(&star), 2);
    }

    #[test]
    fn balanced_tree_uses_both_branches() {
        //        0
        //       / \
        //      1   2
        //     / \
        //    3   4
        // Longest path: 3 - 1 - 0 - 2, three edges.
        let tree = Tree::from_children(&[vec![1, 2], vec![3, 4], vec![], vec![], vec![]]);
        assert_eq!(tree_diameter(&tree), 3);
    }

    #[test]
    fn negative_weights_are_handled() {
        // The six-node tree from the two-sweep module: the true diameter is
        // 5 -- 2 -- 3, weight 3 + 2 = 5, which the two-sweep method misses.
        let tree = Tree::from_weighted_edges(
            6,
            &[(0, 1, 2), (0, 2, -1), (2, 3, 2), (2, 5, 3), (3, 4, -1)],
        );
        assert_eq!(tree_diameter(&tree), 5);

        // When every edge is negative the empty path wins and the answer is 0,
        // exactly as brute force over all simple paths reports: 0 -1- 1 -5- 2
        // offers -1, -5 and -6, all below the empty path's 0.
        let all_negative = Tree::from_weighted_edges(3, &[(0, 1, -1), (1, 2, -5)]);
        assert_eq!(tree_diameter(&all_negative), 0);
    }

    #[test]
    fn agrees_with_brute_force_on_random_trees() {
        // Deterministic PRNG: xorshift64*, seeded once, so failures reproduce.
        let mut state = 0x2545_F491_4F6C_DD1Du64;
        let mut next = move || {
            state ^= state >> 12;
            state ^= state << 25;
            state ^= state >> 27;
            state.wrapping_mul(0x2545_F491_4F6C_DD1D)
        };

        for _ in 0..2_000 {
            let n = (next() % 9 + 1) as usize;
            let mut edges = Vec::new();
            for v in 1..n {
                let parent = (next() % v as u64) as usize;
                // A small spread including negatives keeps both branches of the
                // recurrence exercised.
                let weight = (next() % 7) as i64 - 3;
                edges.push((parent, v, weight));
            }
            let tree = Tree::from_weighted_edges(n, &edges);
            assert_eq!(
                tree_diameter(&tree),
                brute_force(&tree),
                "mismatch on {n} nodes with edges {edges:?}"
            );
        }
    }

    #[test]
    fn deep_chain_does_not_overflow_the_stack() {
        let n = 200_000;
        let mut children = vec![Vec::new(); n];
        for v in 0..n - 1 {
            children[v].push(v + 1);
        }
        let tree = Tree::from_children(&children);
        assert_eq!(tree_diameter(&tree), (n - 1) as i64);
    }
}
