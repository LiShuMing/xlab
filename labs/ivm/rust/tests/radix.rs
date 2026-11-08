use std::collections::BTreeMap;

use ivm_radix_lab::{Aggregate, Error, MinValue, Prefix, RadixTree, Result, SumCount, ZSet};

fn acc(value: i128) -> SumCount {
    SumCount {
        sum: value,
        count: 1,
    }
}

#[test]
fn prefix_boundaries_are_safe() {
    assert_eq!(Prefix::new(123, 0).unwrap(), Prefix::root());
    assert_eq!(Prefix::root().upper(), u64::MAX);
    assert!(Prefix::root().contains(u64::MAX));
    assert_eq!(Prefix::new(0xff, 60).unwrap().key(), 0xf0);
    assert_eq!(Prefix::new(0xff, 60).unwrap().upper(), 0xff);
    for key in [0, 1, 1 << 63, u64::MAX] {
        let p = Prefix::leaf(key);
        assert_eq!((p.key(), p.upper(), p.prefix_len()), (key, key, 64));
        assert!(p.contains(key));
    }
    assert_eq!(Prefix::new(0, 65), Err(Error::InvalidPrefix));
}

#[test]
fn split_compress_replace_and_delete_all() {
    let mut tree = RadixTree::new();
    let mut nodes = ZSet::new();
    for updates in [
        vec![(0, Some(acc(0)))],
        vec![
            (1, Some(acc(4))),
            (2, Some(acc(5))),
            (u64::MAX, Some(acc(-9))),
        ],
        vec![(1, Some(acc(8))), (2, None)],
        vec![(1, None)],
        vec![(0, None), (u64::MAX, None)],
    ] {
        let delta = tree.apply_updates(updates).unwrap();
        nodes.apply_batch(&delta).unwrap();
        assert_eq!(nodes.to_batch(), tree.snapshot());
        assert!(nodes.iter().all(|(_, weight)| weight == 1));
        tree.validate().unwrap();
    }
    assert_eq!(tree.node_count(), 0);
    assert_eq!(tree.query(0, u64::MAX).unwrap(), None);
    assert_eq!(tree.query(2, 1), Err(Error::InvalidRange));
}

#[test]
fn zero_aggregate_is_present_and_full_coverage_reuses_cache() {
    let mut tree = RadixTree::new();
    tree.apply_updates([(0, Some(acc(3))), (1, Some(acc(-3)))])
        .unwrap();
    assert_eq!(
        tree.query(0, 1).unwrap(),
        Some(SumCount { sum: 0, count: 2 })
    );
    let (result, stats) = tree.query_with_stats(0, u64::MAX).unwrap();
    assert!(result.is_some());
    assert_eq!(stats.node_visits, 1);
    assert_eq!(stats.cached_subtrees, 1);
    assert_eq!(tree.query(2, 9).unwrap(), None);
    assert!(tree
        .apply_updates([(1, Some(acc(-3))), (99, None)])
        .unwrap()
        .is_empty());
    tree.apply_updates([(1, Some(acc(8))), (1, Some(acc(4)))])
        .unwrap();
    assert_eq!(tree.query(1, 1).unwrap(), Some(acc(4)));
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
struct Limited(i64);

impl Aggregate for Limited {
    fn combine(&self, other: &Self) -> Result<Self> {
        let value = self
            .0
            .checked_add(other.0)
            .ok_or(Error::AggregateOverflow)?;
        if value > 10 {
            return Err(Error::AggregateOverflow);
        }
        Ok(Self(value))
    }
}

#[test]
fn failed_multikey_update_rolls_back_the_overlay() {
    let mut tree = RadixTree::new();
    tree.apply_updates([(0, Some(Limited(2))), (1, Some(Limited(3)))])
        .unwrap();
    let before = tree.clone();
    assert_eq!(
        tree.apply_updates([(0, Some(Limited(4))), (2, Some(Limited(9)))]),
        Err(Error::AggregateOverflow)
    );
    assert_eq!(tree, before);
    // Also catch overflow across the two root slots.
    assert_eq!(
        tree.apply_updates([(u64::MAX, Some(Limited(9)))]),
        Err(Error::AggregateOverflow)
    );
    assert_eq!(tree, before);
}

#[test]
fn exhaustive_small_domain_and_deterministic_updates() {
    let mut tree = RadixTree::new();
    let mut oracle = BTreeMap::new();
    let mut nodes = ZSet::new();
    let mut state = 42_u64;
    for round in 0..180 {
        let mut updates = Vec::new();
        for _ in 0..5 {
            state = state.wrapping_mul(6364136223846793005).wrapping_add(1);
            let key = (state >> 32) % 16;
            let value = if state & 3 == 0 {
                None
            } else {
                Some(acc((state % 31) as i128 - 15))
            };
            updates.push((key, value));
            match value {
                Some(value) => {
                    oracle.insert(key, value);
                }
                None => {
                    oracle.remove(&key);
                }
            }
        }
        let delta = tree.apply_updates(updates).unwrap();
        nodes.apply_batch(&delta).unwrap();
        assert_eq!(nodes.to_batch(), tree.snapshot(), "round {round}");
        tree.validate().unwrap();
        for from in 0..=16 {
            for to in from..=16 {
                let values: Vec<_> = oracle.range(from..=to).map(|(_, value)| *value).collect();
                let expected = (!values.is_empty()).then(|| SumCount {
                    sum: values.iter().map(|v| v.sum).sum(),
                    count: values.iter().map(|v| v.count).sum(),
                });
                assert_eq!(
                    tree.query(from, to).unwrap(),
                    expected,
                    "round={round}, [{from}, {to}]"
                );
            }
        }
    }
}

#[test]
fn sparse_full_width_keys_against_ordered_scan() {
    let mut tree = RadixTree::<MinValue>::new();
    let mut oracle = BTreeMap::new();
    let keys = [
        0,
        1,
        2,
        (1 << 32) - 1,
        1 << 32,
        (1 << 63) - 1,
        1 << 63,
        u64::MAX - 1,
        u64::MAX,
    ];
    for (index, key) in keys.into_iter().enumerate() {
        oracle.insert(key, MinValue(10 - index as i64));
    }
    tree.apply_updates(oracle.iter().rev().map(|(k, v)| (*k, Some(*v))))
        .unwrap();
    tree.validate().unwrap();
    for from in keys {
        for to in keys.into_iter().filter(|to| *to >= from) {
            let expected = oracle.range(from..=to).map(|(_, v)| *v).min();
            assert_eq!(tree.query(from, to).unwrap(), expected);
        }
    }
}

#[test]
fn full_width_updates_deletions_and_replay() {
    let mut state = 27_u64;
    let mut keys = vec![0, u64::MAX];
    for _ in 0..30 {
        state = state.wrapping_mul(6364136223846793005).wrapping_add(1);
        keys.push(state);
    }
    let mut tree = RadixTree::new();
    let mut oracle = BTreeMap::new();
    let mut nodes = ZSet::new();
    for round in 0..120 {
        let mut updates = Vec::new();
        for _ in 0..4 {
            state = state.wrapping_mul(6364136223846793005).wrapping_add(1);
            let key = keys[((state >> 32) % keys.len() as u64) as usize];
            let value = (state & 3 != 0).then(|| acc((state % 17) as i128 - 8));
            updates.push((key, value));
            if let Some(value) = value {
                oracle.insert(key, value);
            } else {
                oracle.remove(&key);
            }
        }
        nodes
            .apply_batch(&tree.apply_updates(updates).unwrap())
            .unwrap();
        assert_eq!(nodes.to_batch(), tree.snapshot());
        tree.validate().unwrap();
        for from in &keys {
            for to in keys.iter().filter(|to| *to >= from) {
                let values: Vec<_> = oracle.range(*from..=*to).map(|(_, v)| *v).collect();
                let expected = (!values.is_empty()).then(|| SumCount {
                    sum: values.iter().map(|v| v.sum).sum(),
                    count: values.iter().map(|v| v.count).sum(),
                });
                assert_eq!(tree.query(*from, *to).unwrap(), expected, "round {round}");
            }
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
struct Sequence(String);

impl Aggregate for Sequence {
    fn combine(&self, other: &Self) -> Result<Self> {
        Ok(Self(format!("{}{}", self.0, other.0)))
    }
}

#[test]
fn aggregate_preserves_timestamp_order_without_commutativity() {
    let entries = [
        (0, "a"),
        (1, "b"),
        (17, "c"),
        (1 << 63, "d"),
        (u64::MAX, "e"),
    ];
    let mut forward = RadixTree::new();
    let mut reverse = RadixTree::new();
    for (key, value) in entries {
        forward
            .apply_updates([(key, Some(Sequence(value.into())))])
            .unwrap();
    }
    for (key, value) in entries.into_iter().rev() {
        reverse
            .apply_updates([(key, Some(Sequence(value.into())))])
            .unwrap();
    }
    assert_eq!(forward.snapshot(), reverse.snapshot());
    assert_eq!(
        forward.query(0, u64::MAX).unwrap(),
        Some(Sequence("abcde".into()))
    );
    assert_eq!(
        forward.query(1, 1 << 63).unwrap(),
        Some(Sequence("bcd".into()))
    );
    assert_eq!(
        forward.query(2, u64::MAX - 1).unwrap(),
        Some(Sequence("cd".into()))
    );
}
