//! Umbra AI memory database — core engine.

pub mod embedding;
pub mod entity;
pub mod error;
pub mod ops;
pub mod query;
pub mod index;
pub mod storage;
pub mod types;

pub use error::{UmbraError, UmbraResult};
pub use types::*;
