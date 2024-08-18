//! Bloom Filter Library
//!
//! Provides multiple Bloom Filter implementations:
//! - `classic` - Standard Bloom Filter
//! - `split_block` - Cache-efficient Split Block Bloom Filter
//! - `xor_filter` - Memory-efficient XOR Filter

pub mod classic;
pub mod split_block;
pub mod xor_filter;

/// Re-export main types
pub use classic::BloomFilter;
pub use split_block::SplitBlockBloomFilter;
pub use xor_filter::XorFilter;
