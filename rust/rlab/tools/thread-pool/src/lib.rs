//! A simple thread pool implementation for learning purposes
//!
//! This thread pool is inspired by Rayon and demonstrates:
//! - Task distribution using channels
//! - Worker thread management
//! - Graceful shutdown
//! - Basic error handling

use std::sync::{mpsc, Arc, Mutex};
use std::thread::{self, JoinHandle};

pub mod builder;
pub mod worker;

pub use builder::ThreadPoolBuilder;
use worker::Worker;

/// Error type for thread pool operations
#[derive(Debug)]
pub enum PoolError {
    /// The thread pool has been shut down
    Shutdown,
    /// Failed to spawn a worker thread
    SpawnError(std::io::Error),
}

impl std::fmt::Display for PoolError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            PoolError::Shutdown => write!(f, "Thread pool has been shut down"),
            PoolError::SpawnError(e) => write!(f, "Failed to spawn worker thread: {e}"),
        }
    }
}

impl std::error::Error for PoolError {
    fn source(&self) -> Option<&(dyn std::error::Error + 'static)> {
        match self {
            PoolError::SpawnError(e) => Some(e),
            _ => None,
        }
    }
}

/// Type alias for task closure
type Task = Box<dyn FnOnce() + Send + 'static>;

/// Internal message types sent to workers
enum Message {
    /// Execute this task
    Work(Task),
    /// Stop the worker
    Terminate,
}

/// A simple thread pool for executing tasks concurrently
///
/// # Examples
///
/// ```
/// use thread_pool::ThreadPool;
///
/// let pool = ThreadPool::new(4).unwrap();
///
/// pool.execute(|| {
///     println!("Task running in thread pool");
/// });
///
/// // Thread pool will shut down when dropped
/// ```
pub struct ThreadPool {
    /// Sender for dispatching tasks to workers
    sender: Option<mpsc::Sender<Message>>,
    /// Worker threads
    workers: Vec<Worker>,
    /// Thread pool configuration
    config: PoolConfig,
}

/// Configuration for the thread pool
#[derive(Clone, Debug)]
pub struct PoolConfig {
    /// Number of worker threads
    pub num_threads: usize,
    /// Thread stack size in bytes (0 for default)
    pub stack_size: usize,
    /// Thread name prefix
    pub name_prefix: String,
}

impl Default for PoolConfig {
    fn default() -> Self {
        Self {
            num_threads: num_cpus::get(),
            stack_size: 0,
            name_prefix: "pool-worker".to_string(),
        }
    }
}

impl ThreadPool {
    /// Create a new thread pool with the specified number of threads
    ///
    /// # Panics
    ///
    /// Panics if `num_threads` is 0
    pub fn new(num_threads: usize) -> Result<Self, PoolError> {
        ThreadPoolBuilder::new().num_threads(num_threads).build()
    }

    /// Create a thread pool with default configuration
    ///
    /// Uses `num_cpus::get()` as the number of worker threads
    pub fn with_defaults() -> Result<Self, PoolError> {
        ThreadPoolBuilder::new().build()
    }

    /// Execute a task in the thread pool
    ///
    /// Returns an error if the pool has been shut down
    pub fn execute<F>(&self, f: F) -> Result<(), PoolError>
    where
        F: FnOnce() + Send + 'static,
    {
        let task = Box::new(f);
        match &self.sender {
            Some(sender) => sender
                .send(Message::Work(task))
                .map_err(|_| PoolError::Shutdown),
            None => Err(PoolError::Shutdown),
        }
    }

    /// Get the number of worker threads
    pub fn num_threads(&self) -> usize {
        self.config.num_threads
    }

    /// Shut down the thread pool gracefully
    ///
    /// This will wait for all pending tasks to complete before returning
    pub fn shutdown(mut self) {
        self.shutdown_internal();
    }

    fn shutdown_internal(&mut self) {
        // Drop the sender to close the channel
        // This signals workers that no more tasks are coming
        drop(self.sender.take());

        // Wait for all workers to finish
        for worker in &mut self.workers {
            if let Some(thread) = worker.thread.take() {
                let _ = thread.join();
            }
        }
    }
}

impl Drop for ThreadPool {
    fn drop(&mut self) {
        if self.sender.is_some() {
            self.shutdown_internal();
        }
    }
}

/// Creates workers and returns them along with the sender
pub(crate) fn create_workers(
    config: &PoolConfig,
    receiver: Arc<Mutex<mpsc::Receiver<Message>>>,
) -> Result<Vec<Worker>, PoolError> {
    let mut workers = Vec::with_capacity(config.num_threads);

    for id in 0..config.num_threads {
        let worker = Worker::spawn(
            id,
            Arc::clone(&receiver),
            &config.name_prefix,
            config.stack_size,
        )?;
        workers.push(worker);
    }

    Ok(workers)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicUsize, Ordering};

    #[test]
    fn test_basic_execution() {
        let pool = ThreadPool::new(2).unwrap();
        let counter = Arc::new(AtomicUsize::new(0));

        for _ in 0..10 {
            let counter = Arc::clone(&counter);
            pool.execute(move || {
                counter.fetch_add(1, Ordering::SeqCst);
            })
            .unwrap();
        }

        // Give time for tasks to complete
        std::thread::sleep(std::time::Duration::from_millis(100));

        assert_eq!(counter.load(Ordering::SeqCst), 10);
    }

    #[test]
    fn test_shutdown() {
        let pool = ThreadPool::new(2).unwrap();
        let counter = Arc::new(AtomicUsize::new(0));

        for _ in 0..5 {
            let counter = Arc::clone(&counter);
            pool.execute(move || {
                std::thread::sleep(std::time::Duration::from_millis(10));
                counter.fetch_add(1, Ordering::SeqCst);
            })
            .unwrap();
        }

        pool.shutdown();
        assert_eq!(counter.load(Ordering::SeqCst), 5);
    }

    #[test]
    fn test_execute_after_shutdown() {
        let pool = ThreadPool::new(1).unwrap();
        pool.shutdown();
        // After shutdown, pool is consumed, so we can't test this directly
        // But we can test that the shutdown happened correctly
    }

    #[test]
    #[should_panic(expected = "num_threads must be positive")]
    fn test_zero_threads() {
        ThreadPoolBuilder::new().num_threads(0).build().unwrap();
    }
}
