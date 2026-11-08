use ivm_radix_lab::{Batch, Error, IndexedBatch, ZSet};

#[test]
fn canonical_weights_and_projection() {
    let z = ZSet::from_updates([(3, 0), (2, 4), (1, -2), (2, -4)]).unwrap();
    assert_eq!(z.len(), 1);
    assert!(!z.contains(&3));
    assert_eq!(z.weight(&1), -2);
    assert_eq!(z.weight(&2), 0);
    let z = ZSet::from_updates([(1, 3), (2, -3), (3, 2)]).unwrap();
    assert_eq!(z.map(|_| 0).unwrap(), ZSet::from_updates([(0, 2)]).unwrap());
    assert_eq!(z.filter(|key| *key < 3).map(|_| 0).unwrap(), ZSet::new());
}

#[test]
fn join_multiplies_and_consolidates() {
    let left = ZSet::from_updates([(1, 3), (2, -3)]).unwrap();
    let right = ZSet::from_updates([(7, 2)]).unwrap();
    assert!(left.join(&right, |_, _| Some(0)).unwrap().is_empty());
    assert_eq!(
        left.join(&right, |a, b| (*a == 1).then_some(a + b))
            .unwrap()
            .weight(&8),
        6
    );
    let huge = ZSet::from_updates([(0, i64::MAX)]).unwrap();
    assert_eq!(
        huge.join(&right, |_, _| Some(0)),
        Err(Error::WeightOverflow)
    );
}

#[test]
fn group_laws_with_bounded_weights() {
    for seed in 0..64 {
        let a = ZSet::from_updates([(1, seed), (2, -seed)]).unwrap();
        let b = ZSet::from_updates([(1, -3), (3, 4)]).unwrap();
        let c = ZSet::from_updates([(2, 2), (3, -1)]).unwrap();
        assert_eq!(a.added(&ZSet::new()).unwrap(), a);
        assert_eq!(a.added(&a.negated().unwrap()).unwrap(), ZSet::new());
        assert_eq!(a.added(&b).unwrap(), b.added(&a).unwrap());
        assert_eq!(
            a.added(&b).unwrap().added(&c).unwrap(),
            a.added(&b.added(&c).unwrap()).unwrap()
        );
    }
}

#[test]
fn wide_consolidation_and_atomic_overflow() {
    for weights in [[i64::MAX, 1, -1], [-1, 1, i64::MAX], [1, i64::MAX, -1]] {
        let updates = weights.map(|w| (0, w));
        assert_eq!(
            Batch::from_updates(updates).unwrap(),
            ZSet::from_updates(updates).unwrap().to_batch()
        );
        assert_eq!(ZSet::from_updates(updates).unwrap().weight(&0), i64::MAX);
    }
    let mut z = ZSet::from_updates([(2, i64::MAX)]).unwrap();
    let before = z.clone();
    assert_eq!(z.add_weight(2, 1), Err(Error::WeightOverflow));
    assert_eq!(z, before);
    let delta = Batch::from_updates([(1, 9), (2, 1)]).unwrap();
    assert_eq!(z.apply_batch(&delta), Err(Error::WeightOverflow));
    assert_eq!(z, before);
    let min = ZSet::from_updates([(0, i64::MIN)]).unwrap();
    assert_eq!(min.negated(), Err(Error::WeightOverflow));
    assert_eq!(min.to_batch().negated(), Err(Error::WeightOverflow));
    assert_eq!(
        Batch::from_updates([(0, i64::MAX), (0, 1)]),
        Err(Error::WeightOverflow)
    );
}

#[test]
fn batches_sort_merge_and_cancel_against_map_oracle() {
    for seed in 0..100_i64 {
        let updates: Vec<_> = (0..50)
            .map(|n| ((n * 17 + seed) % 11, (n + seed) % 7 - 3))
            .collect();
        let (a, b) = updates.split_at(23);
        let a = Batch::from_updates(a.iter().copied()).unwrap();
        let b = Batch::from_updates(b.iter().copied()).unwrap();
        let oracle = ZSet::from_updates(updates).unwrap().to_batch();
        assert_eq!(a.merged(&b).unwrap(), oracle);
        assert_eq!(
            oracle.merged(&oracle.negated().unwrap()).unwrap(),
            Batch::default()
        );
        assert_eq!(oracle.merged(&Batch::default()).unwrap(), oracle);
    }
    let huge = Batch::from_updates([(0, i64::MAX)]).unwrap();
    assert_eq!(huge.merged(&huge), Err(Error::WeightOverflow));
}

#[test]
fn grouped_cursor_forward_seek_and_rewind() {
    let batch = IndexedBatch::from_updates([
        ((3, 7), 2),
        ((1, 4), 1),
        ((1, 2), -1),
        ((3, 7), -1),
        ((2, 0), 0),
    ])
    .unwrap();
    assert_eq!((batch.len(), batch.key_count()), (3, 2));
    let mut cursor = batch.cursor();
    assert_eq!(
        (cursor.key(), cursor.value(), cursor.weight()),
        (Some(&1), Some(&2), Some(-1))
    );
    cursor.seek_value(&3);
    assert_eq!(cursor.value(), Some(&4));
    cursor.seek_value(&1);
    assert_eq!(cursor.value(), Some(&4));
    cursor.step_value();
    cursor.seek_key(&1);
    assert_eq!(cursor.value(), None);
    cursor.seek_key(&2);
    assert_eq!(
        (cursor.key(), cursor.value(), cursor.weight()),
        (Some(&3), Some(&7), Some(1))
    );
    cursor.seek_key(&0);
    assert_eq!(cursor.key(), Some(&3));
    cursor.step_key();
    assert_eq!(
        (cursor.key(), cursor.value(), cursor.weight()),
        (None, None, None)
    );
    cursor.seek_key(&0);
    cursor.step_value();
    cursor.step_key();
    assert_eq!(cursor.key(), None);
    cursor.rewind();
    assert_eq!(cursor.key(), Some(&1));
    cursor.seek_value(&100);
    cursor.seek_value(&0);
    assert_eq!(cursor.value(), None);
    cursor.seek_key(&100);
    assert_eq!(cursor.key(), None);
}

#[test]
fn empty_cursor_is_total() {
    let batch = IndexedBatch::<u64, i64>::from_updates([]).unwrap();
    assert!(batch.is_empty());
    assert_eq!(batch.key_count(), 0);
    let mut c = batch.cursor();
    c.seek_key(&9);
    c.seek_value(&7);
    c.step_key();
    c.step_value();
    c.rewind();
    assert_eq!((c.key(), c.value(), c.weight()), (None, None, None));
}
