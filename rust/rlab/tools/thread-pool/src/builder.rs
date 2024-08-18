//! Thread pool builder for configurable pool creation

use crate::{create_workers, Message, PoolConfig, PoolError, ThreadPool};
use std::sync::{mpsc, Arc, Mutex};

/// Builder for constructing a [`ThreadPool`](crate::ThreadPool) with custom configuration
///
/// # Examples
///
/// ```
/// use thread_pool::ThreadPoolBuilder;
///
/// let pool = ThreadPoolBuilder::new()
///     .num_threads(8)
///     .stack_size(2 * 1024 * 1024)  // 2MB stack
///     .name_prefix("compute".to_string())
///     .build()
///     .unwrap();
/// ```
#[derive(Debug)]
pub struct ThreadPoolBuilder {
    config: PoolConfig,
}

impl ThreadPoolBuilder {
    /// Create a new builder with default configuration
    pub fn new() -> Self {
        Self {
            config: PoolConfig::default(),
        }
    }

    /// Set the number of worker threads
    ///
    /// Defaults to the number of logical CPUs on the system
    pub fn num_threads(mut self, num_threads: usize) -> Self {
        self.config.num_threads = num_threads;
        self
    }

    /// Set the stack size for worker threads
    ///
    /// Defaults to the system default (usually 2MB on most systems)
    pub fn stack_size(mut self, stack_size: usize) -> Self {
        self.config.stack_size = stack_size;
        self
    }

    /// Set the name prefix for worker threads
    ///
    /// Worker threads will be named `{prefix}-{id}`
    pub fn name_prefix(mut self, prefix: String) -> Self {
        self.config.name_prefix = prefix;
        self
    }

    /// Build the thread pool with the configured settings
    ///
    /// # Errors
    ///
    /// Returns an error if:
    /// - `num_threads` is 0
    /// - A worker thread fails to spawn
    pub fn build(self) -> Result<ThreadPool, PoolError> {
        if self.config.num_threads == 0 {
            return Err(PoolError::SpawnError(std::io::Error::new(
                std::io::ErrorKind::InvalidInput,
                "num_threads must be positive",
            )));
        }

        let (sender, receiver) = mpsc::channel();
        let receiver = Arc::new(Mutex::new(receiver));

        let workers = create_workers(&self.config, receiver)?;

        Ok(ThreadPool {
            sender: Some(sender),
            workers,
            config: self.config,
        })
    }
}

impl Default for ThreadPoolBuilder {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_builder_chain() {
        let pool = ThreadPoolBuilder::new()
            .num_threads(4)
            .stack_size(1024 * 1024)
            .name_prefix("test".to_string())
            .build()
            .unwrap();

        assert_eq!(pool.num_threads(), 4);
    }

    #[test]
    fn test_default_builder() {
        let pool = ThreadPoolBuilder::new().build().unwrap();
        assert_eq!(pool.num_threads(), num_cpus::get());
    }
}
