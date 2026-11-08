//! Two-level sorted storage and a forward-only grouped cursor.

use crate::{Batch, Result};

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct IndexedBatch<K, V> {
    keys: Vec<K>,
    offsets: Vec<usize>,
    values: Vec<V>,
    weights: Vec<i64>,
}

impl<K: Ord, V: Ord> IndexedBatch<K, V> {
    pub fn from_updates(updates: impl IntoIterator<Item = ((K, V), i64)>) -> Result<Self> {
        Ok(Self::from_batch(Batch::from_updates(updates)?))
    }

    pub fn from_batch(batch: Batch<(K, V)>) -> Self {
        let mut result = Self {
            keys: vec![],
            offsets: vec![0],
            values: vec![],
            weights: vec![],
        };
        for ((key, value), weight) in batch.into_entries() {
            if result.keys.last() != Some(&key) {
                if !result.keys.is_empty() {
                    result.offsets.push(result.values.len());
                }
                result.keys.push(key);
            }
            result.values.push(value);
            result.weights.push(weight);
        }
        if !result.keys.is_empty() {
            result.offsets.push(result.values.len());
        }
        result
    }

    pub fn len(&self) -> usize {
        self.values.len()
    }

    pub fn is_empty(&self) -> bool {
        self.values.is_empty()
    }

    pub fn key_count(&self) -> usize {
        self.keys.len()
    }

    pub fn cursor(&self) -> Cursor<'_, K, V> {
        Cursor {
            batch: self,
            key_pos: 0,
            value_pos: 0,
        }
    }
}

/// Seeking never moves backward. Rewind explicitly before an earlier lookup.
pub struct Cursor<'a, K, V> {
    batch: &'a IndexedBatch<K, V>,
    key_pos: usize,
    value_pos: usize,
}

impl<'a, K: Ord, V: Ord> Cursor<'a, K, V> {
    pub fn key(&self) -> Option<&'a K> {
        self.batch.keys.get(self.key_pos)
    }

    pub fn value(&self) -> Option<&'a V> {
        if self.key().is_some() && self.value_pos < self.batch.offsets[self.key_pos + 1] {
            self.batch.values.get(self.value_pos)
        } else {
            None
        }
    }

    pub fn weight(&self) -> Option<i64> {
        self.value().map(|_| self.batch.weights[self.value_pos])
    }

    pub fn step_key(&mut self) {
        if self.key_pos < self.batch.keys.len() {
            self.key_pos += 1;
            self.value_pos = self.batch.offsets[self.key_pos];
        }
    }

    pub fn step_value(&mut self) {
        if self.value().is_some() {
            self.value_pos += 1;
        }
    }

    pub fn seek_key(&mut self, target: &K) {
        let advance = self.batch.keys[self.key_pos..].partition_point(|key| key < target);
        if advance > 0 {
            self.key_pos += advance;
            self.value_pos = self.batch.offsets[self.key_pos];
        }
    }

    pub fn seek_value(&mut self, target: &V) {
        if self.key().is_some() {
            let end = self.batch.offsets[self.key_pos + 1];
            self.value_pos +=
                self.batch.values[self.value_pos..end].partition_point(|value| value < target);
        }
    }

    pub fn rewind(&mut self) {
        self.key_pos = 0;
        self.value_pos = 0;
    }
}
