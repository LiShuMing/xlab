//! Sorted, unique, zero-free immutable batches.

use std::cmp::Ordering;

use crate::{narrow_weight, Error, Result};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Batch<T> {
    entries: Vec<(T, i64)>,
}

impl<T> Default for Batch<T> {
    fn default() -> Self {
        Self { entries: vec![] }
    }
}

impl<T: Ord> Batch<T> {
    /// Consolidate in i128 before narrowing so cancellation is order-independent
    /// within the representable accumulator domain.
    pub fn from_updates(updates: impl IntoIterator<Item = (T, i64)>) -> Result<Self> {
        let mut updates: Vec<_> = updates.into_iter().collect();
        updates.sort_unstable_by(|a, b| a.0.cmp(&b.0));
        let mut sums: Vec<(T, i128)> = Vec::new();
        for (item, weight) in updates {
            if let Some((last, sum)) = sums.last_mut() {
                if last == &item {
                    *sum = sum
                        .checked_add(i128::from(weight))
                        .ok_or(Error::WeightOverflow)?;
                    continue;
                }
            }
            sums.push((item, i128::from(weight)));
        }
        let entries = sums
            .into_iter()
            .filter(|(_, weight)| *weight != 0)
            .map(|(item, weight)| Ok((item, narrow_weight(weight)?)))
            .collect::<Result<_>>()?;
        Ok(Self { entries })
    }

    pub fn iter(&self) -> impl Iterator<Item = (&T, i64)> {
        self.entries.iter().map(|(item, weight)| (item, *weight))
    }

    pub fn len(&self) -> usize {
        self.entries.len()
    }

    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    pub fn into_entries(self) -> Vec<(T, i64)> {
        self.entries
    }

    pub fn negated(&self) -> Result<Self>
    where
        T: Clone,
    {
        let entries = self
            .iter()
            .map(|(item, weight)| {
                Ok((
                    item.clone(),
                    weight.checked_neg().ok_or(Error::WeightOverflow)?,
                ))
            })
            .collect::<Result<_>>()?;
        Ok(Self { entries })
    }

    /// Linear merge of already consolidated inputs; no sorting is needed.
    pub fn merged(&self, other: &Self) -> Result<Self>
    where
        T: Clone,
    {
        let (mut left, mut right) = (0, 0);
        let mut entries = Vec::with_capacity(self.len() + other.len());
        while left < self.len() && right < other.len() {
            let (a, wa) = &self.entries[left];
            let (b, wb) = &other.entries[right];
            match a.cmp(b) {
                Ordering::Less => {
                    entries.push((a.clone(), *wa));
                    left += 1;
                }
                Ordering::Greater => {
                    entries.push((b.clone(), *wb));
                    right += 1;
                }
                Ordering::Equal => {
                    let weight = narrow_weight(i128::from(*wa) + i128::from(*wb))?;
                    if weight != 0 {
                        entries.push((a.clone(), weight));
                    }
                    left += 1;
                    right += 1;
                }
            }
        }
        entries.extend_from_slice(&self.entries[left..]);
        entries.extend_from_slice(&other.entries[right..]);
        Ok(Self { entries })
    }

    pub(crate) fn from_canonical(entries: Vec<(T, i64)>) -> Self {
        debug_assert!(entries.iter().all(|(_, weight)| *weight != 0));
        debug_assert!(entries.windows(2).all(|pair| pair[0].0 < pair[1].0));
        Self { entries }
    }
}
