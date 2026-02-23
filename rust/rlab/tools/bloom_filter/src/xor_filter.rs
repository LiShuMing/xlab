//! XOR Filter Implementation
//!
//! An efficient probabilistic data structure that uses less memory than Bloom Filters.
//! Based on "Xor Filters: Faster and Smaller Than Bloom and Cuckoo Filters" by Graf and Lemire.
//!
//! The XOR Filter uses a fuse graph structure and assigns values to slots such that
//! for each element, the XOR of its three mapped slots equals a fingerprint.
//!
//! Key advantages:
//! - ~30% less memory than Bloom Filter for same FP rate
//! - O(1) lookups with 3 memory accesses
//! - No false negatives
//! - Immutable after construction (must know all items upfront)

use ahash::AHasher;
use std::hash::{Hash, Hasher};

/// Number of hash functions (typically 3 for XOR filters)
const HASHES: usize = 3;

/// XOR Filter
///
/// Uses a fuse graph with 3 hash functions per item.
/// Construction is O(n) average case using peeling algorithm.
#[derive(Clone, Debug)]
pub struct XorFilter {
    /// The fingerprint array
    fingerprints: Vec<u8>, // 8-bit fingerprints
    /// Number of slots (typically 1.23x the number of items)
    num_slots: usize,
    /// Number of items
    num_items: usize,
    /// Seed for hashing
    seed: u64,
}

/// A struct to hold the three hash positions for an item
#[derive(Clone, Copy, Debug)]
struct HashPositions {
    h0: usize,
    h1: usize,
    h2: usize,
}

impl XorFilter {
    /// Build a new XOR Filter from a collection of items
    ///
    /// # Arguments
    /// * `items` - Iterator of items to insert
    ///
    /// # Returns
    /// * `Some(XorFilter)` if construction succeeds
    /// * `None` if construction fails (very rare with proper sizing)
    pub fn from_items<T: Hash, I: Iterator<Item = T>>(items: I) -> Option<Self> {
        let items: Vec<T> = items.collect();
        let num_items = items.len();
        
        if num_items == 0 {
            return Some(Self {
                fingerprints: vec![],
                num_slots: 0,
                num_items: 0,
                seed: 0,
            });
        }
        
        // Size factor: 1.23 is optimal for 3-hash fuse graphs
        let size_factor = 1.23;
        let num_slots = ((num_items as f64 * size_factor).ceil() as usize).max(HASHES);
        
        // Try different seeds until construction succeeds
        for seed in 0..100 {
            if let Some(filter) = Self::try_build(&items, num_slots, seed) {
                return Some(filter);
            }
        }
        
        None
    }

    /// Try to build the filter with given parameters
    fn try_build<T: Hash>(items: &[T], num_slots: usize, seed: u64) -> Option<Self> {
        let num_items = items.len();
        
        // Step 1: Build the fuse graph and find peeling order
        // Store: (item_idx, [h0, h1, h2], peel_slot_idx)
        let mut stack: Vec<(usize, [usize; HASHES], usize)> = Vec::with_capacity(items.len());
        let mut count = vec![0u32; num_slots]; // Use u32 to avoid overflow with large datasets
        let mut hash_pos: Vec<HashPositions> = Vec::with_capacity(items.len());
        
        // Count occurrences of each slot
        for item in items {
            let pos = Self::hash_positions(item, num_slots, seed);
            hash_pos.push(pos);
            count[pos.h0] += 1;
            count[pos.h1] += 1;
            count[pos.h2] += 1;
        }
        
        // Queue for peeling: slots with count = 1
        let mut queue: Vec<usize> = count.iter()
            .enumerate()
            .filter(|(_, &c)| c == 1)
            .map(|(i, _)| i)
            .collect();
        
        // Peeling algorithm
        // Store: (item_idx, [h0, h1, h2], peel_slot_idx)
        // peel_slot_idx is which of the three slots had count 1 when peeled
        let mut processed = vec![false; items.len()];
        while let Some(slot) = queue.pop() {
            // Find item with this slot
            for (i, pos) in hash_pos.iter().enumerate() {
                if processed[i] {
                    continue;
                }
                let item_slot_idx = if pos.h0 == slot { 0 }
                    else if pos.h1 == slot { 1 }
                    else if pos.h2 == slot { 2 }
                    else { continue };
                
                processed[i] = true;
                let slots = [pos.h0, pos.h1, pos.h2];
                // Store which slot was the "peel slot" (count = 1)
                stack.push((i, slots, item_slot_idx));
                
                // Decrement counts for the other two slots
                for j in 0..HASHES {
                    if j != item_slot_idx {
                        count[slots[j]] = count[slots[j]].saturating_sub(1);
                        if count[slots[j]] == 1 {
                            queue.push(slots[j]);
                        }
                    }
                }
                break;
            }
        }
        
        // Check if all items were processed
        if stack.len() != items.len() {
            return None; // Failed to peel, try different seed
        }
        
        // Step 2: Assign fingerprints
        let mut fingerprints = vec![0u8; num_slots];
        
        while let Some((item_idx, slots, peel_slot_idx)) = stack.pop() {
            let item = &items[item_idx];
            let fp = Self::fingerprint(item, seed);
            
            // Get the other two slot indices
            let other_slots: Vec<usize> = (0..HASHES)
                .filter(|&i| i != peel_slot_idx)
                .map(|i| slots[i])
                .collect();
            
            // The peel slot's value = fp ^ other_slot1 ^ other_slot2
            let xor = fingerprints[other_slots[0]] ^ fingerprints[other_slots[1]];
            fingerprints[slots[peel_slot_idx]] = fp ^ xor;
        }
        
        Some(Self {
            fingerprints,
            num_slots,
            num_items,
            seed,
        })
    }

    /// Check if an item might be in the filter
    pub fn contains<T: Hash>(&self, item: &T) -> bool {
        if self.num_slots == 0 {
            return false;
        }
        
        let pos = Self::hash_positions(item, self.num_slots, self.seed);
        let fp = Self::fingerprint(item, self.seed);
        
        let xor = self.fingerprints[pos.h0] 
            ^ self.fingerprints[pos.h1] 
            ^ self.fingerprints[pos.h2];
        
        xor == fp
    }

    /// Get the number of items
    pub fn len(&self) -> usize {
        self.num_items
    }

    pub fn is_empty(&self) -> bool {
        self.num_items == 0
    }

    /// Get memory usage in bytes
    pub fn memory_usage(&self) -> usize {
        self.fingerprints.len()
    }

    /// Get number of slots
    pub fn num_slots(&self) -> usize {
        self.num_slots
    }

    /// Theoretical false positive rate: ~1/256 for 8-bit fingerprints
    pub fn theoretical_fp_rate(&self) -> f64 {
        1.0 / 256.0
    }

    /// Calculate three hash positions for an item
    fn hash_positions<T: Hash>(item: &T, num_slots: usize, seed: u64) -> HashPositions {
        let hash = Self::hash64(item, seed);
        
        // Use different parts of the 64-bit hash
        // Ensure num_slots > 0 to avoid division by zero
        let num_slots = num_slots.max(1);
        let h0 = (hash as u32 as usize).wrapping_rem(num_slots);
        let h1 = ((hash >> 21) as u32 as usize).wrapping_rem(num_slots);
        let h2 = ((hash >> 42) as u32 as usize).wrapping_rem(num_slots);
        
        HashPositions { h0, h1, h2 }
    }

    /// Calculate 8-bit fingerprint for an item
    fn fingerprint<T: Hash>(item: &T, seed: u64) -> u8 {
        let hash = Self::hash64(item, seed.wrapping_add(0x9e3779b97f4a7c15));
        hash as u8
    }

    /// 64-bit hash of item
    fn hash64<T: Hash>(item: &T, seed: u64) -> u64 {
        let mut hasher = AHasher::default();
        seed.hash(&mut hasher);
        item.hash(&mut hasher);
        hasher.finish()
    }
}

/// Builder for XorFilter to handle construction more flexibly
pub struct XorFilterBuilder<T: Hash> {
    items: Vec<T>,
}

impl<T: Hash> XorFilterBuilder<T> {
    pub fn new() -> Self {
        Self { items: vec![] }
    }

    pub fn with_capacity(capacity: usize) -> Self {
        Self { items: Vec::with_capacity(capacity) }
    }

    pub fn add(&mut self, item: T) {
        self.items.push(item);
    }

    pub fn build(self) -> Option<XorFilter> {
        XorFilter::from_items(self.items.into_iter())
    }
}

impl<T: Hash> Default for XorFilterBuilder<T> {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_basic_construction() {
        let items: Vec<i32> = (0..100).collect();
        let filter = XorFilter::from_items(items.into_iter()).expect("Construction should succeed");
        
        assert_eq!(filter.len(), 100);
        assert!(filter.memory_usage() < 150); // Should be ~123 bytes
    }

    #[test]
    fn test_no_false_negatives() {
        let items: Vec<i32> = (0..1000).collect();
        let filter = XorFilter::from_items(items.clone().into_iter()).unwrap();
        
        for item in &items {
            assert!(filter.contains(item), "Item {} should be found", item);
        }
    }

    #[test]
    fn test_fp_rate_approximation() {
        let items: Vec<i32> = (0..10000).collect();
        let filter = XorFilter::from_items(items.clone().into_iter()).unwrap();
        
        // Test with items not in the set
        let mut false_positives = 0;
        let test_count = 10000;
        
        for i in 10000..20000 {
            if filter.contains(&i) {
                false_positives += 1;
            }
        }
        
        let fp_rate = false_positives as f64 / test_count as f64;
        println!("False positive rate: {:.4}%", fp_rate * 100.0);
        
        // Should be close to 1/256 (~0.39%)
        assert!(fp_rate < 0.01, "FP rate should be < 1%");
    }

    #[test]
    fn test_memory_efficiency() {
        let items: Vec<i32> = (0..100000).collect();
        let filter = XorFilter::from_items(items.into_iter()).unwrap();
        
        let bytes_per_item = filter.memory_usage() as f64 / 100000.0;
        println!("Bytes per item: {:.2}", bytes_per_item);
        
        // XOR filter uses ~1.23 bytes per item for 8-bit fingerprints
        assert!(bytes_per_item < 2.0);
    }

    #[test]
    fn test_builder() {
        let mut builder = XorFilterBuilder::new();
        for i in 0..100 {
            builder.add(i);
        }
        
        let filter = builder.build().expect("Build should succeed");
        assert_eq!(filter.len(), 100);
    }

    #[test]
    fn test_empty() {
        let filter = XorFilter::from_items(std::iter::empty::<i32>()).unwrap();
        assert!(filter.is_empty());
        assert!(!filter.contains(&42));
    }
    
    #[test]
    fn test_small_set() {
        // Test with a very small set
        let items = vec![1, 2, 3];
        let filter = XorFilter::from_items(items.clone().into_iter()).unwrap();
        
        for item in &items {
            assert!(filter.contains(item), "Item {} should be found", item);
        }
        
        // Check non-existent items
        assert!(!filter.contains(&4));
        assert!(!filter.contains(&100));
    }
}
