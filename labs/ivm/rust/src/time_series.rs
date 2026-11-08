//! Recompute affected timestamp buckets, then maintain the range index.

use std::{collections::BTreeSet, marker::PhantomData};

use crate::{radix_tree::NodeDelta, Aggregate, Batch, Error, RadixTree, Result, ZSet};

pub trait Aggregator {
    type Acc: Aggregate;

    /// Values are consolidated, positive multiplicities from one timestamp.
    fn reduce(values: impl Iterator<Item = (i64, i64)>) -> Result<Option<Self::Acc>>;
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub struct SumCount {
    pub sum: i128,
    pub count: i128,
}

impl Aggregate for SumCount {
    fn combine(&self, other: &Self) -> Result<Self> {
        Ok(Self {
            sum: self
                .sum
                .checked_add(other.sum)
                .ok_or(Error::AggregateOverflow)?,
            count: self
                .count
                .checked_add(other.count)
                .ok_or(Error::AggregateOverflow)?,
        })
    }
}

pub struct SumCountAggregator;

impl Aggregator for SumCountAggregator {
    type Acc = SumCount;

    fn reduce(values: impl Iterator<Item = (i64, i64)>) -> Result<Option<SumCount>> {
        let mut result: Option<SumCount> = None;
        for (value, weight) in values {
            if weight <= 0 {
                return Err(Error::NegativeMultiplicity);
            }
            let next = SumCount {
                sum: i128::from(value) * i128::from(weight),
                count: i128::from(weight),
            };
            result = Some(match result {
                None => next,
                Some(acc) => acc.combine(&next)?,
            });
        }
        Ok(result)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub struct MinValue(pub i64);

impl Aggregate for MinValue {
    fn combine(&self, other: &Self) -> Result<Self> {
        Ok(Self(self.0.min(other.0)))
    }
}

pub struct Minimum;

impl Aggregator for Minimum {
    type Acc = MinValue;

    fn reduce(values: impl Iterator<Item = (i64, i64)>) -> Result<Option<MinValue>> {
        let mut result: Option<MinValue> = None;
        for (value, weight) in values {
            if weight <= 0 {
                return Err(Error::NegativeMultiplicity);
            }
            result = Some(MinValue(result.map_or(value, |acc| acc.0.min(value))));
        }
        Ok(result)
    }
}

pub struct TimeSeries<G: Aggregator> {
    input: ZSet<(u64, i64)>,
    tree: RadixTree<G::Acc>,
    reducer: PhantomData<G>,
}

impl<G: Aggregator> Default for TimeSeries<G> {
    fn default() -> Self {
        Self {
            input: ZSet::new(),
            tree: RadixTree::new(),
            reducer: PhantomData,
        }
    }
}

impl<G: Aggregator> TimeSeries<G> {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn input(&self) -> &ZSet<(u64, i64)> {
        &self.input
    }

    pub fn tree(&self) -> &RadixTree<G::Acc> {
        &self.tree
    }

    pub fn query(&self, from: u64, to: u64) -> Result<Option<G::Acc>> {
        self.tree.query(from, to)
    }

    /// Atomic educational transaction. Input cloning costs O(N); only the tree
    /// index is path-local. This is not a production trace implementation.
    pub fn apply_batch(&mut self, delta: &Batch<(u64, i64)>) -> Result<NodeDelta<G::Acc>> {
        let mut next_input = self.input.clone();
        next_input.apply_batch(delta)?;
        let times: BTreeSet<_> = delta.iter().map(|((timestamp, _), _)| *timestamp).collect();
        let mut updates = Vec::with_capacity(times.len());
        for timestamp in times {
            if next_input
                .range((timestamp, i64::MIN)..=(timestamp, i64::MAX))
                .any(|(_, weight)| weight < 0)
            {
                return Err(Error::NegativeMultiplicity);
            }
            let values = next_input.range((timestamp, i64::MIN)..=(timestamp, i64::MAX));
            let aggregate = G::reduce(values.map(|((_, value), weight)| (*value, weight)))?;
            updates.push((timestamp, aggregate));
        }
        let node_delta = self.tree.apply_updates(updates)?;
        self.input = next_input;
        Ok(node_delta)
    }
}
