//! Integration tests for the tree diameter algorithms.
//!
//! These tests use `rlab` as an external consumer would: they only touch the
//! public API. Their job is not to re-check the worked examples in the unit
//! tests but to assert the relationship between the two implementations — they
//! must agree on every tree where both are in scope, and the returned path must
//! actually be a path of the reported weight.

use rlab::common::graph::{tree_diameter, tree_diameter_path, tree_dp, Tree};

/// Deterministic xorshift64* so a failure reproduces from the seed alone.
struct Rng(u64);

impl Rng {
    fn next(&mut self) -> u64 {
        self.0 ^= self.0 >> 12;
        self.0 ^= self.0 << 25;
        self.0 ^= self.0 >> 27;
        self.0.wrapping_mul(0x2545_F491_4F6C_DD1D)
    }

    fn below(&mut self, bound: u64) -> u64 {
        self.next() % bound
    }
}

/// A random tree on `n` nodes with weights drawn from `low..=high`.
fn random_tree(rng: &mut Rng, n: usize, low: i64, high: i64) -> Tree {
    let span = (high - low + 1) as u64;
    let mut edges = Vec::with_capacity(n.saturating_sub(1));
    for v in 1..n {
        let parent = rng.below(v as u64) as usize;
        let weight = low + rng.below(span) as i64;
        edges.push((parent, v, weight));
    }
    Tree::from_weighted_edges(n, &edges)
}

/// Longest simple path found by walking every simple path from every node.
fn brute_force(tree: &Tree) -> i64 {
    let mut best = 0;
    for start in 0..tree.node_count() {
        let mut stack = vec![(start, usize::MAX, 0i64)];
        while let Some((v, from, total)) = stack.pop() {
            best = best.max(total);
            for (to, w) in tree.neighbors(v) {
                if to != from {
                    stack.push((to, v, total + w));
                }
            }
        }
    }
    best
}

/// Total weight of `path`, or `None` if it is not a simple walk in `tree`.
fn weigh_path(tree: &Tree, path: &[usize]) -> Option<i64> {
    let mut seen = vec![false; tree.node_count()];
    for &v in path {
        if seen[v] {
            return None; // a diameter path never revisits a node
        }
        seen[v] = true;
    }

    let mut total = 0;
    for pair in path.windows(2) {
        let (from, to) = (pair[0], pair[1]);
        let (_, w) = tree.neighbors(from).find(|&(n, _)| n == to)?;
        total += w;
    }
    Some(total)
}

#[test]
fn both_implementations_agree_with_brute_force() {
    let mut rng = Rng(0x9E37_79B9_7F4A_7C15);
    for _ in 0..2_000 {
        let n = rng.below(10) as usize + 1;
        // Non-negative weights so the two-sweep precondition holds and all
        // three answers are expected to coincide.
        let tree = random_tree(&mut rng, n, 0, 4);
        let expected = brute_force(&tree);
        assert_eq!(tree_diameter(&tree), expected, "two-sweep on {tree:?}");
        assert_eq!(tree_dp::tree_diameter(&tree), expected, "tree-dp on {tree:?}");
    }
}

#[test]
fn tree_dp_agrees_with_brute_force_for_negative_weights() {
    let mut rng = Rng(0xDEAD_BEEF_CAFE_F00D);
    for _ in 0..2_000 {
        let n = rng.below(9) as usize + 1;
        // Negative weights are out of scope for the sweeps but must not move
        // the DP off the brute-force answer.
        let tree = random_tree(&mut rng, n, -3, 3);
        assert_eq!(tree_dp::tree_diameter(&tree), brute_force(&tree), "{tree:?}");
    }
}

#[test]
fn reported_path_matches_its_length() {
    let mut rng = Rng(0x0123_4567_89AB_CDEF);
    for _ in 0..1_000 {
        let n = rng.below(12) as usize + 1;
        let tree = random_tree(&mut rng, n, 0, 5);
        let (length, path) = tree_diameter_path(&tree);
        assert_eq!(length, tree_diameter(&tree), "length disagrees on {tree:?}");
        assert_eq!(
            weigh_path(&tree, &path),
            Some(length),
            "path {path:?} does not weigh {length} in {tree:?}"
        );
    }
}

#[test]
fn hand_built_shapes_match_both_methods() {
    // Path of five nodes.
    let path = Tree::from_children(&[vec![1], vec![2], vec![3], vec![4], vec![]]);
    assert_eq!(tree_diameter(&path), 4);
    assert_eq!(tree_dp::tree_diameter(&path), 4);

    // Star with four leaves.
    let star = Tree::from_children(&[vec![1, 2, 3, 4], vec![], vec![], vec![], vec![]]);
    assert_eq!(tree_diameter(&star), 2);
    assert_eq!(tree_dp::tree_diameter(&star), 2);

    // Balanced binary tree, three levels.
    let balanced =
        Tree::from_children(&[vec![1, 2], vec![3, 4], vec![5, 6], vec![], vec![], vec![], vec![]]);
    assert_eq!(tree_diameter(&balanced), 4);
    assert_eq!(tree_dp::tree_diameter(&balanced), 4);
}

#[test]
fn the_two_methods_diverge_only_on_negative_weights() {
    // The documented six-node counterexample: identical trees, opposite answers
    // once an edge turns negative.
    let tree = Tree::from_weighted_edges(
        6,
        &[(0, 1, 2), (0, 2, -1), (2, 3, 2), (2, 5, 3), (3, 4, -1)],
    );
    assert!(!tree.has_non_negative_weights());
    assert_eq!(tree_dp::tree_diameter(&tree), 5);

    // Flip every weight positive and the sweep catches up.
    let non_negative = Tree::from_weighted_edges(
        6,
        &[(0, 1, 2), (0, 2, 1), (2, 3, 2), (2, 5, 3), (3, 4, 1)],
    );
    assert!(non_negative.has_non_negative_weights());
    assert_eq!(tree_diameter(&non_negative), tree_dp::tree_diameter(&non_negative));
}
