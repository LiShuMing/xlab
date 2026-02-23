//! Classic Bloom Filter Implementation
//!
//! A standard bloom filter using multiple hash functions and a bit array.

use ahash::AHasher;
use std::hash::{Hash, Hasher};

/// Classic Bloom Filter
///
/// Uses k independent hash functions to set k bits in a bit array.
/// False positive rate: approximately (1 - e^(-kn/m))^k
/// where n = items, m = bits, k = hash functions
#[derive(Clone, Debug)]
pub struct BloomFilter {
    bits: Vec<u64>,  // Bit array stored as u64 chunks for efficiency
    num_bits: usize,
    num_hashes: usize,
    num_items: usize,
}

impl BloomFilter {
    /// Create a new Bloom Filter with target capacity and false positive rate
    ///
    /// # Arguments
    /// * `capacity` - Expected number of items to insert
    /// * `fp_rate` - Target false positive rate (e.g., 0.01 for 1%)
    pub fn new(capacity: usize, fp_rate: f64) -> Self {
        // Optimal number of bits: m = -n * ln(p) / (ln(2)^2)
        let num_bits = ((-(capacity as f64) * fp_rate.ln()) / (2.0_f64.ln().powi(2))).ceil() as usize;
        // Optimal number of hash functions: k = m/n * ln(2)
        let num_hashes = ((num_bits as f64 / capacity as f64) * 2.0_f64.ln()).round() as usize;
        
        // Ensure at least 1 hash function
        let num_hashes = num_hashes.max(1);
        // Round up bits to multiple of 64
        let num_u64s = (num_bits + 63) / 64;
        
        Self {
            bits: vec![0; num_u64s],
            num_bits: num_u64s * 64,
            num_hashes,
            num_items: 0,
        }
    }

    /// Create with specific parameters
    pub fn with_params(num_bits: usize, num_hashes: usize) -> Self {
        let num_u64s = (num_bits + 63) / 64;
        Self {
            bits: vec![0; num_u64s],
            num_bits: num_u64s * 64,
            num_hashes,
            num_items: 0,
        }
    }

    /// Insert an item into the filter
    pub fn insert<T: Hash>(&mut self, item: &T) {
        for i in 0..self.num_hashes {
            let idx = self.hash_index(item, i);
            self.set_bit(idx);
        }
        self.num_items += 1;
    }

    /// Check if an item might be in the filter
    /// Returns true if possibly present, false if definitely not present
    pub fn contains<T: Hash>(&self, item: &T) -> bool {
        for i in 0..self.num_hashes {
            let idx = self.hash_index(item, i);
            if !self.get_bit(idx) {
                return false;
            }
        }
        true
    }

    /// Get the number of items inserted
    pub fn len(&self) -> usize {
        self.num_items
    }

    /// Check if filter is empty
    pub fn is_empty(&self) -> bool {
        self.num_items == 0
    }

    /// Get the size in bits
    pub fn num_bits(&self) -> usize {
        self.num_bits
    }

    /// Get the number of hash functions
    pub fn num_hashes(&self) -> usize {
        self.num_hashes
    }

    /// Get approximate memory usage in bytes
    pub fn memory_usage(&self) -> usize {
        self.bits.len() * 8
    }

    /// Estimate current false positive rate
    pub fn current_fp_rate(&self) -> f64 {
        // (1 - e^(-kn/m))^k
        let exponent = -(self.num_hashes as f64 * self.num_items as f64) / self.num_bits as f64;
        (1.0 - exponent.exp()).powi(self.num_hashes as i32)
    }

    /// Clear all items from the filter
    pub fn clear(&mut self) {
        self.bits.fill(0);
        self.num_items = 0;
    }

    /// Hash an item to get bit index for the i-th hash function
    fn hash_index<T: Hash>(&self, item: &T, seed: usize) -> usize {
        let mut hasher = AHasher::default();
        item.hash(&mut hasher);
        seed.hash(&mut hasher);
        let hash = hasher.finish();
        (hash as usize) % self.num_bits
    }

    /// Set a bit in the bit array
    #[inline]
    fn set_bit(&mut self, idx: usize) {
        let (word, bit) = (idx / 64, idx % 64);
        self.bits[word] |= 1u64 << bit;
    }

    /// Get a bit from the bit array
    #[inline]
    fn get_bit(&self, idx: usize) -> bool {
        let (word, bit) = (idx / 64, idx % 64);
        (self.bits[word] >> bit) & 1 == 1
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_basic_operations() {
        let mut bf = BloomFilter::new(1000, 0.01);
        
        bf.insert(&"hello");
        bf.insert(&"world");
        
        assert!(bf.contains(&"hello"));
        assert!(bf.contains(&"world"));
        assert!(!bf.contains(&"unknown"));
        
        assert_eq!(bf.len(), 2);
    }

    #[test]
    fn test_no_false_negatives() {
        let mut bf = BloomFilter::new(1000, 0.01);
        
        // Insert 100 items
        for i in 0..100 {
            bf.insert(&i);
        }
        
        // All inserted items should be found
        for i in 0..100 {
            assert!(bf.contains(&i), "Item {} should be found", i);
        }
    }

    #[test]
    fn test_clear() {
        let mut bf = BloomFilter::new(100, 0.01);
        bf.insert(&"test");
        assert!(bf.contains(&"test"));
        
        bf.clear();
        assert!(!bf.contains(&"test"));
        assert_eq!(bf.len(), 0);
    }

    #[test]
    fn test_memory_usage() {
        let bf = BloomFilter::new(10000, 0.01);
        let bytes = bf.memory_usage();
        // Should be approximately 12kb for 10k items at 1% fp rate
        assert!(bytes > 0);
        println!("Memory usage: {} bytes for {} items", bytes, 10000);
    }
}
