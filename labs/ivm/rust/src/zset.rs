//! BTreeMap-backed semantic reference for finite integer-weighted collections.

use std::{collections::BTreeMap, ops::RangeBounds};

use crate::{narrow_weight, Batch, Error, Result};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ZSet<T: Ord> {
    weights: BTreeMap<T, i64>,
}

impl<T: Ord> Default for ZSet<T> {
    fn default() -> Self {
        Self {
            weights: BTreeMap::new(),
        }
    }
}

impl<T: Ord> ZSet<T> {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn from_updates(updates: impl IntoIterator<Item = (T, i64)>) -> Result<Self> {
        Self::from_wide(
            updates
                .into_iter()
                .map(|(item, weight)| (item, i128::from(weight))),
        )
    }

    fn from_wide(updates: impl IntoIterator<Item = (T, i128)>) -> Result<Self> {
        let mut sums = BTreeMap::<T, i128>::new();
        for (item, weight) in updates {
            let sum = sums.entry(item).or_default();
            *sum = sum.checked_add(weight).ok_or(Error::WeightOverflow)?;
        }
        let weights = sums
            .into_iter()
            .filter(|(_, weight)| *weight != 0)
            .map(|(item, weight)| Ok((item, narrow_weight(weight)?)))
            .collect::<Result<_>>()?;
        Ok(Self { weights })
    }

    pub fn weight(&self, item: &T) -> i64 {
        self.weights.get(item).copied().unwrap_or(0)
    }

    pub fn contains(&self, item: &T) -> bool {
        self.weights.contains_key(item)
    }

    pub fn len(&self) -> usize {
        self.weights.len()
    }

    pub fn is_empty(&self) -> bool {
        self.weights.is_empty()
    }

    pub fn iter(&self) -> impl Iterator<Item = (&T, i64)> {
        self.weights.iter().map(|(item, weight)| (item, *weight))
    }

    pub fn range(&self, bounds: impl RangeBounds<T>) -> impl Iterator<Item = (&T, i64)> {
        self.weights
            .range(bounds)
            .map(|(item, weight)| (item, *weight))
    }

    pub fn add_weight(&mut self, item: T, delta: i64) -> Result<()> {
        let next = narrow_weight(i128::from(self.weight(&item)) + i128::from(delta))?;
        if next == 0 {
            self.weights.remove(&item);
        } else {
            self.weights.insert(item, next);
        }
        Ok(())
    }

    /// Preflight every weight before modifying any item.
    pub fn apply_batch(&mut self, batch: &Batch<T>) -> Result<()>
    where
        T: Clone,
    {
        let pending = batch
            .iter()
            .map(|(item, delta)| {
                Ok((
                    item.clone(),
                    narrow_weight(i128::from(self.weight(item)) + i128::from(delta))?,
                ))
            })
            .collect::<Result<Vec<_>>>()?;
        for (item, weight) in pending {
            if weight == 0 {
                self.weights.remove(&item);
            } else {
                self.weights.insert(item, weight);
            }
        }
        Ok(())
    }

    pub fn to_batch(&self) -> Batch<T>
    where
        T: Clone,
    {
        Batch::from_canonical(
            self.iter()
                .map(|(item, weight)| (item.clone(), weight))
                .collect(),
        )
    }

    pub fn added(&self, other: &Self) -> Result<Self>
    where
        T: Clone,
    {
        Self::from_wide(
            self.iter()
                .chain(other.iter())
                .map(|(item, weight)| (item.clone(), i128::from(weight))),
        )
    }

    pub fn negated(&self) -> Result<Self>
    where
        T: Clone,
    {
        Self::from_wide(
            self.iter()
                .map(|(item, weight)| (item.clone(), -i128::from(weight))),
        )
    }

    /// Projection can merge different input records, including cancellations.
    pub fn map<U: Ord>(&self, mut project: impl FnMut(&T) -> U) -> Result<ZSet<U>> {
        ZSet::from_wide(
            self.iter()
                .map(|(item, weight)| (project(item), i128::from(weight))),
        )
    }

    pub fn filter(&self, mut keep: impl FnMut(&T) -> bool) -> Self
    where
        T: Clone,
    {
        Self {
            weights: self
                .iter()
                .filter(|(item, _)| keep(item))
                .map(|(item, weight)| (item.clone(), weight))
                .collect(),
        }
    }

    /// Teaching nested-loop join. None means the pair does not match.
    pub fn join<U: Ord, O: Ord>(
        &self,
        other: &ZSet<U>,
        mut project: impl FnMut(&T, &U) -> Option<O>,
    ) -> Result<ZSet<O>> {
        let mut updates = Vec::new();
        for (left, left_weight) in self.iter() {
            for (right, right_weight) in other.iter() {
                if let Some(output) = project(left, right) {
                    updates.push((output, i128::from(left_weight) * i128::from(right_weight)));
                }
            }
        }
        ZSet::from_wide(updates)
    }
}
