//! Split Block Bloom Filter (SBBF)
//!
//! A cache-efficient Bloom Filter that divides the bit array into fixed-size blocks.
//! Each item maps to one block and sets multiple bits within that block using SIMD-friendly
//! operations.
//!
//! This design improves cache locality and allows for SIMD optimization.

use ahash::AHasher;
use std::hash::{Hash, Hasher};

/// Size of each block in bits (typically 256 bits = 4 u64s for cache line alignment)
const BLOCK_BITS: usize = 256;
const BLOCK_U64S: usize = BLOCK_BITS / 64;

/// Split Block Bloom Filter
///
/// Similar to classic Bloom Filter but each item maps to a single block
/// and uses 8 hash functions within that block.
#[derive(Clone, Debug)]
pub struct SplitBlockBloomFilter {
    blocks: Vec<[u64; BLOCK_U64S]>, // Each block is 4 u64s = 256 bits
    num_blocks: usize,
    num_items: usize,
    num_hashes_per_block: usize, // Typically 8 for 256-bit blocks
}

impl SplitBlockBloomFilter {
    /// Create a new SBBF with target capacity and false positive rate
    pub fn new(capacity: usize, fp_rate: f64) -> Self {
        // For SBBF with 8 hashes per block, optimal block size calculation
        // Similar to classic BF but with block-level organization
        let bits_needed = ((-(capacity as f64) * fp_rate.ln()) / (2.0_f64.ln().powi(2))).ceil() as usize;
        let num_blocks = (bits_needed + BLOCK_BITS - 1) / BLOCK_BITS;
        
        // Use 8 hashes per block for 256-bit blocks
        let num_hashes_per_block = 8;
        
        Self {
            blocks: vec![[0u64; BLOCK_U64S]; num_blocks],
            num_blocks,
            num_items: 0,
            num_hashes_per_block,
        }
    }

    /// Create with specific number of blocks
    pub fn with_blocks(num_blocks: usize) -> Self {
        Self {
            blocks: vec![[0u64; BLOCK_U64S]; num_blocks],
            num_blocks,
            num_items: 0,
            num_hashes_per_block: 8,
        }
    }

    /// Insert an item into the filter
    pub fn insert<T: Hash>(&mut self, item: &T) {
        let (block_idx, hashes) = self.hash_item(item);
        let block = &mut self.blocks[block_idx];
        
        // Set bits within the block using the 8 hash values
        for i in 0..self.num_hashes_per_block {
            let bit_idx = (hashes[i] as usize) % BLOCK_BITS;
            let word_idx = bit_idx / 64;
            let bit_offset = bit_idx % 64;
            block[word_idx] |= 1u64 << bit_offset;
        }
        
        self.num_items += 1;
    }

    /// Check if an item might be in the filter
    pub fn contains<T: Hash>(&self, item: &T) -> bool {
        let (block_idx, hashes) = self.hash_item(item);
        let block = &self.blocks[block_idx];
        
        // Check all 8 bits in the block
        for i in 0..self.num_hashes_per_block {
            let bit_idx = (hashes[i] as usize) % BLOCK_BITS;
            let word_idx = bit_idx / 64;
            let bit_offset = bit_idx % 64;
            
            if (block[word_idx] >> bit_offset) & 1 == 0 {
                return false;
            }
        }
        
        true
    }

    /// Insert an item (batch-friendly version that returns block index)
    /// Useful for SIMD batch processing
    pub fn insert_raw(&mut self, block_idx: usize, hashes: &[u32; 8]) {
        let block = &mut self.blocks[block_idx];
        
        for i in 0..self.num_hashes_per_block {
            let bit_idx = (hashes[i] as usize) % BLOCK_BITS;
            let word_idx = bit_idx / 64;
            let bit_offset = bit_idx % 64;
            block[word_idx] |= 1u64 << bit_offset;
        }
        
        self.num_items += 1;
    }

    /// Check if item exists (batch-friendly version)
    pub fn contains_raw(&self, block_idx: usize, hashes: &[u32; 8]) -> bool {
        let block = &self.blocks[block_idx];
        
        for i in 0..self.num_hashes_per_block {
            let bit_idx = (hashes[i] as usize) % BLOCK_BITS;
            let word_idx = bit_idx / 64;
            let bit_offset = bit_idx % 64;
            
            if (block[word_idx] >> bit_offset) & 1 == 0 {
                return false;
            }
        }
        
        true
    }

    /// Hash an item to get block index and 8 bit positions
    fn hash_item<T: Hash>(&self, item: &T) -> (usize, [u32; 8]) {
        let mut hasher = AHasher::default();
        item.hash(&mut hasher);
        let hash = hasher.finish();
        
        // Use first 32 bits for block selection
        let block_idx = (hash as u32 as usize) % self.num_blocks;
        
        // Generate 8 hash values from the 64-bit hash
        // Using splitmix64-like mixing for additional hashes
        let mut hashes = [0u32; 8];
        let mut h = hash;
        for i in 0..8 {
            h = h.wrapping_mul(0x9e3779b97f4a7c15);
            h = (h ^ (h >> 30)).wrapping_mul(0xbf58476d1ce4e5b9);
            h = (h ^ (h >> 27)).wrapping_mul(0x94d049bb133111eb);
            h = h ^ (h >> 31);
            hashes[i] = h as u32;
        }
        
        (block_idx, hashes)
    }

    /// Get the number of items inserted
    pub fn len(&self) -> usize {
        self.num_items
    }

    pub fn is_empty(&self) -> bool {
        self.num_items == 0
    }

    /// Get the number of blocks
    pub fn num_blocks(&self) -> usize {
        self.num_blocks
    }

    /// Get total bits
    pub fn num_bits(&self) -> usize {
        self.num_blocks * BLOCK_BITS
    }

    /// Get memory usage in bytes
    pub fn memory_usage(&self) -> usize {
        self.num_blocks * BLOCK_U64S * 8
    }

    /// Get the number of hash functions per block
    pub fn num_hashes_per_block(&self) -> usize {
        self.num_hashes_per_block
    }

    /// Estimate current false positive rate
    pub fn current_fp_rate(&self) -> f64 {
        // For each block: (1 - (1 - 1/BLOCK_BITS)^k)^k where k = num_hashes_per_block
        let block_fp = (1.0 - (1.0 - 1.0 / BLOCK_BITS as f64).powi(self.num_hashes_per_block as i32))
            .powi(self.num_hashes_per_block as i32);
        block_fp
    }

    /// Clear all items
    pub fn clear(&mut self) {
        for block in &mut self.blocks {
            *block = [0u64; BLOCK_U64S];
        }
        self.num_items = 0;
    }

    /// Get raw block data (for advanced usage)
    pub fn blocks(&self) -> &[[u64; BLOCK_U64S]] {
        &self.blocks
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_basic_operations() {
        let mut bf = SplitBlockBloomFilter::new(1000, 0.01);
        
        bf.insert(&"hello");
        bf.insert(&"world");
        
        assert!(bf.contains(&"hello"));
        assert!(bf.contains(&"world"));
        assert!(!bf.contains(&"unknown"));
    }

    #[test]
    fn test_no_false_negatives() {
        let mut bf = SplitBlockBloomFilter::new(1000, 0.01);
        
        for i in 0..100 {
            bf.insert(&i);
        }
        
        for i in 0..100 {
            assert!(bf.contains(&i));
        }
    }

    #[test]
    fn test_block_structure() {
        let bf = SplitBlockBloomFilter::new(10000, 0.01);
        
        // Should use 256-bit blocks (4 u64s each)
        assert_eq!(BLOCK_BITS, 256);
        assert_eq!(BLOCK_U64S, 4);
        
        // Memory should be a multiple of 32 bytes per block
        assert!(bf.memory_usage() % 32 == 0);
    }

    #[test]
    fn test_cache_alignment() {
        // Each block is 32 bytes (4 u64s), which fits in a cache line
        assert!(std::mem::size_of::<[u64; BLOCK_U64S]>() <= 64);
    }
}
