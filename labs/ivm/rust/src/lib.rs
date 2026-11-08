//! Integer-weighted collections and incremental time-range aggregation.
//!
//! This is an independent teaching implementation, not a DBSP runtime.
//!
//! ```
//! use ivm_radix_lab::{Batch, SumCount, SumCountAggregator, TimeSeries};
//!
//! let mut series = TimeSeries::<SumCountAggregator>::new();
//! series.apply_batch(&Batch::from_updates([((10, 3), 2), ((20, 7), 1)])?)?;
//! assert_eq!(series.query(10, 20)?, Some(SumCount { sum: 13, count: 3 }));
//! series.apply_batch(&Batch::from_updates([((10, 3), -2)])?)?;
//! assert_eq!(series.query(10, 20)?, Some(SumCount { sum: 7, count: 1 }));
//! # Ok::<(), ivm_radix_lab::Error>(())
//! ```
#![forbid(unsafe_code)]

pub mod batch;
pub mod indexed_batch;
pub mod radix_tree;
pub mod time_series;
pub mod zset;

use std::fmt;

pub use batch::Batch;
pub use indexed_batch::{Cursor, IndexedBatch};
pub use radix_tree::{Aggregate, Child, NodeDelta, Prefix, QueryStats, RadixTree, TreeNode};
pub use time_series::{Aggregator, MinValue, Minimum, SumCount, SumCountAggregator, TimeSeries};
pub use zset::ZSet;

/// Arithmetic and input errors leave mutable collection state unchanged.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Error {
    WeightOverflow,
    AggregateOverflow,
    NegativeMultiplicity,
    InvalidRange,
    InvalidPrefix,
    CorruptTree,
}

impl fmt::Display for Error {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(match self {
            Self::WeightOverflow => "integer weight overflow",
            Self::AggregateOverflow => "aggregate overflow",
            Self::NegativeMultiplicity => "a materialized event has negative multiplicity",
            Self::InvalidRange => "range start exceeds range end",
            Self::InvalidPrefix => "prefix length must be in 0..=64",
            Self::CorruptTree => "radix-tree structural invariant violated",
        })
    }
}

impl std::error::Error for Error {}

pub type Result<T> = std::result::Result<T, Error>;

pub(crate) fn narrow_weight(value: i128) -> Result<i64> {
    i64::try_from(value).map_err(|_| Error::WeightOverflow)
}
