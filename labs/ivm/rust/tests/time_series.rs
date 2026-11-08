use std::collections::BTreeMap;

use ivm_radix_lab::{
    Batch, Error, MinValue, Minimum, SumCount, SumCountAggregator, TimeSeries, ZSet,
};

#[test]
fn duplicates_retractions_and_minimum_recovery() {
    let mut sum = TimeSeries::<SumCountAggregator>::new();
    let mut min = TimeSeries::<Minimum>::new();
    let insert = Batch::from_updates([((10, 3), 2), ((10, 7), 1), ((20, -2), 1)]).unwrap();
    sum.apply_batch(&insert).unwrap();
    min.apply_batch(&insert).unwrap();
    assert_eq!(
        sum.query(10, 20).unwrap(),
        Some(SumCount { sum: 11, count: 4 })
    );
    assert_eq!(min.query(10, 10).unwrap(), Some(MinValue(3)));
    let retract = Batch::from_updates([((10, 3), -2)]).unwrap();
    sum.apply_batch(&retract).unwrap();
    min.apply_batch(&retract).unwrap();
    assert_eq!(min.query(10, 10).unwrap(), Some(MinValue(7)));
    assert_eq!(
        sum.query(10, 20).unwrap(),
        Some(SumCount { sum: 5, count: 2 })
    );
    // Processing order is not event time: an old timestamp may arrive later.
    let late = Batch::from_updates([((0, 0), 1), ((u64::MAX, 0), 1)]).unwrap();
    sum.apply_batch(&late).unwrap();
    assert_eq!(
        sum.query(0, 0).unwrap(),
        Some(SumCount { sum: 0, count: 1 })
    );
    assert_eq!(
        sum.query(u64::MAX, u64::MAX).unwrap(),
        Some(SumCount { sum: 0, count: 1 })
    );
}

#[test]
fn invalid_retraction_and_overflows_are_atomic() {
    let mut series = TimeSeries::<SumCountAggregator>::new();
    series
        .apply_batch(&Batch::from_updates([((1, 1), i64::MAX)]).unwrap())
        .unwrap();
    let input = series.input().clone();
    let tree = series.tree().clone();
    let invalid = Batch::from_updates([((0, 9), 1), ((1, 8), -1)]).unwrap();
    assert_eq!(
        series.apply_batch(&invalid),
        Err(Error::NegativeMultiplicity)
    );
    assert_eq!(series.input(), &input);
    assert_eq!(series.tree(), &tree);
    let overflow = Batch::from_updates([((0, 9), 1), ((1, 1), 1)]).unwrap();
    assert_eq!(series.apply_batch(&overflow), Err(Error::WeightOverflow));
    assert_eq!(series.input(), &input);
    assert_eq!(series.tree(), &tree);
    let overflow = Batch::from_updates([
        ((2, i64::MAX), i64::MAX),
        ((2, i64::MAX - 1), i64::MAX),
        ((2, i64::MAX - 2), i64::MAX),
    ])
    .unwrap();
    assert_eq!(series.apply_batch(&overflow), Err(Error::AggregateOverflow));
    assert_eq!(series.input(), &input);
    assert_eq!(series.tree(), &tree);
    // Overflow only when combining different timestamps: tree rollback must
    // also protect the independently materialized input state.
    let overflow = Batch::from_updates([
        ((2, i64::MAX), i64::MAX),
        ((3, i64::MAX), i64::MAX),
        ((4, i64::MAX), i64::MAX),
    ])
    .unwrap();
    assert_eq!(series.apply_batch(&overflow), Err(Error::AggregateOverflow));
    assert_eq!(series.input(), &input);
    assert_eq!(series.tree(), &tree);
}

#[test]
fn cancellation_and_deleting_the_last_event() {
    let mut series = TimeSeries::<Minimum>::new();
    let empty = Batch::from_updates([((7, 2), -1), ((7, 2), 1)]).unwrap();
    assert!(series.apply_batch(&empty).unwrap().is_empty());
    let insert = Batch::from_updates([((7, 2), 1)]).unwrap();
    series.apply_batch(&insert).unwrap();
    // Replacing the minimum's multiplicity changes input, but not its index.
    assert!(series.apply_batch(&insert).unwrap().is_empty());
    let delete = Batch::from_updates([((7, 2), -2)]).unwrap();
    series.apply_batch(&delete).unwrap();
    assert!(series.input().is_empty());
    assert_eq!(series.tree().node_count(), 0);
    assert_eq!(series.query(7, 7).unwrap(), None);
}

#[test]
fn incremental_sum_min_and_node_deltas_match_full_recomputation() {
    let mut sum = TimeSeries::<SumCountAggregator>::new();
    let mut min = TimeSeries::<Minimum>::new();
    let mut oracle = BTreeMap::<(u64, i64), i64>::new();
    let mut sum_nodes = ZSet::new();
    let mut min_nodes = ZSet::new();
    let mut state = 17_u64;
    for round in 0..240 {
        let mut updates = Vec::new();
        for _ in 0..7 {
            state = state
                .wrapping_mul(2862933555777941757)
                .wrapping_add(3037000493);
            let timestamp = match state % 11 {
                0 => 0,
                1 => u64::MAX,
                _ => (state >> 24) % 12,
            };
            let value = ((state >> 40) % 13) as i64 - 6;
            let next = ((state >> 16) % 4) as i64;
            let old = oracle.get(&(timestamp, value)).copied().unwrap_or(0);
            updates.push(((timestamp, value), next - old));
            if next == 0 {
                oracle.remove(&(timestamp, value));
            } else {
                oracle.insert((timestamp, value), next);
            }
        }
        let batch = Batch::from_updates(updates).unwrap();
        sum_nodes
            .apply_batch(&sum.apply_batch(&batch).unwrap())
            .unwrap();
        min_nodes
            .apply_batch(&min.apply_batch(&batch).unwrap())
            .unwrap();
        assert_eq!(sum_nodes.to_batch(), sum.tree().snapshot());
        assert_eq!(min_nodes.to_batch(), min.tree().snapshot());
        assert_eq!(
            sum.input().to_batch(),
            Batch::from_updates(oracle.iter().map(|(k, w)| (*k, *w))).unwrap()
        );
        sum.tree().validate().unwrap();
        min.tree().validate().unwrap();
        let bounds = [0, 1, 3, 7, 11, 12, u64::MAX];
        for from in bounds {
            for to in bounds.into_iter().filter(|to| *to >= from) {
                let values: Vec<_> = oracle
                    .iter()
                    .filter(|((ts, _), _)| from <= *ts && *ts <= to)
                    .collect();
                let expected = (!values.is_empty()).then(|| SumCount {
                    sum: values
                        .iter()
                        .map(|((_, v), w)| i128::from(*v) * i128::from(**w))
                        .sum(),
                    count: values.iter().map(|(_, w)| i128::from(**w)).sum(),
                });
                let expected_min = values.iter().map(|((_, v), _)| MinValue(*v)).min();
                assert_eq!(sum.query(from, to).unwrap(), expected, "round {round}");
                assert_eq!(min.query(from, to).unwrap(), expected_min, "round {round}");
            }
        }
    }
}
