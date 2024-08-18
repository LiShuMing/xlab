//! Lock-free queue implementations for learning concurrency
//!
//! This crate provides lock-free queue implementations to understand:
//! - Atomic operations (Relaxed, Acquire, Release, AcqRel, SeqCst)
//! - Memory ordering semantics
//! - ABA problem and solutions
//! - Cache coherence and false sharing
//!
//! # Queue Types
//!
//! - [`MpmcQueue`]: Multi-Producer Multi-Consumer queue
//! - [`MpscQueue`]: Multi-Producer Single-Consumer queue (optimized)

use std::ptr::null_mut;
use std::sync::atomic::{AtomicPtr, AtomicUsize, Ordering};

pub mod mpmc;
pub mod mpsc;

pub use mpmc::MpmcQueue;
pub use mpsc::MpscQueue;

/// Error types for queue operations
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum QueueError {
    /// The queue is full
    Full,
    /// The queue is empty
    Empty,
    /// The queue has been closed
    Closed,
}

impl std::fmt::Display for QueueError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            QueueError::Full => write!(f, "Queue is full"),
            QueueError::Empty => write!(f, "Queue is empty"),
            QueueError::Closed => write!(f, "Queue is closed"),
        }
    }
}

impl std::error::Error for QueueError {}

/// A node in the linked-list based queue
#[repr(align(64))] // Prevent false sharing
pub struct Node<T> {
    /// The data stored in this node
    data: Option<T>,
    /// Pointer to the next node
    next: AtomicPtr<Node<T>>,
}

impl<T> Node<T> {
    /// Create a new node
    pub fn new(data: T) -> Self {
        Self {
            data: Some(data),
            next: AtomicPtr::new(null_mut()),
        }
    }

    /// Create a dummy node (for head/tail initialization)
    pub fn dummy() -> Self {
        Self {
            data: None,
            next: AtomicPtr::new(null_mut()),
        }
    }
}

/// Memory ordering helpers
pub mod ordering {
    use std::sync::atomic::Ordering;

    /// For load operations that need to see all previous stores
    pub const LOAD: Ordering = Ordering::Acquire;
    /// For store operations that need to be seen by subsequent loads
    pub const STORE: Ordering = Ordering::Release;
    /// For read-modify-write operations
    pub const RMW: Ordering = Ordering::AcqRel;
    /// For operations that need total ordering
    pub const SEQ_CST: Ordering = Ordering::SeqCst;
    /// For operations that don't need synchronization
    pub const RELAXED: Ordering = Ordering::Relaxed;
}

/// Statistics for queue operations (for debugging/learning)
#[derive(Debug, Default)]
pub struct QueueStats {
    /// Number of successful pushes
    pub push_count: AtomicUsize,
    /// Number of successful pops
    pub pop_count: AtomicUsize,
    /// Number of failed pushes (full)
    pub push_fail_count: AtomicUsize,
    /// Number of failed pops (empty)
    pub pop_fail_count: AtomicUsize,
}

impl QueueStats {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn record_push(&self) {
        self.push_count.fetch_add(1, Ordering::Relaxed);
    }

    pub fn record_push_fail(&self) {
        self.push_fail_count.fetch_add(1, Ordering::Relaxed);
    }

    pub fn record_pop(&self) {
        self.pop_count.fetch_add(1, Ordering::Relaxed);
    }

    pub fn record_pop_fail(&self) {
        self.pop_fail_count.fetch_add(1, Ordering::Relaxed);
    }
}

/// Check if architecture supports double-word CAS (needed for some algorithms)
#[cfg(target_arch = "x86_64")]
pub const HAS_DW_CAS: bool = true;

#[cfg(not(target_arch = "x86_64"))]
pub const HAS_DW_CAS: bool = false;

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Arc;
    use std::thread;

    #[test]
    fn test_mpmc_basic() {
        let queue = Arc::new(MpmcQueue::<i32>::new());

        // Single thread operations
        queue.push(1).unwrap();
        queue.push(2).unwrap();
        queue.push(3).unwrap();

        assert_eq!(queue.pop().unwrap(), 1);
        assert_eq!(queue.pop().unwrap(), 2);
        assert_eq!(queue.pop().unwrap(), 3);
        assert!(matches!(queue.pop(), Err(QueueError::Empty)));
    }

    #[test]
    fn test_mpmc_multi_threaded() {
        let queue = Arc::new(MpmcQueue::<i32>::new());
        let mut handles = vec![];

        // Multiple producers
        for i in 0..4 {
            let q = Arc::clone(&queue);
            handles.push(thread::spawn(move || {
                for j in 0..100 {
                    q.push(i * 100 + j).unwrap();
                }
            }));
        }

        // Wait for producers
        for h in handles {
            h.join().unwrap();
        }

        // Verify all items were pushed
        let mut count = 0;
        while queue.pop().is_ok() {
            count += 1;
        }
        assert_eq!(count, 400);
    }

    #[test]
    fn test_mpsc_basic() {
        let queue = Arc::new(MpscQueue::<i32>::new());

        queue.push(1).unwrap();
        queue.push(2).unwrap();
        queue.push(3).unwrap();

        assert_eq!(queue.pop().unwrap(), 1);
        assert_eq!(queue.pop().unwrap(), 2);
        assert_eq!(queue.pop().unwrap(), 3);
    }

    #[test]
    fn test_mpsc_multi_producer() {
        let queue = Arc::new(MpscQueue::<i32>::new());
        let mut handles = vec![];

        // Multiple producers
        for i in 0..4 {
            let q = Arc::clone(&queue);
            handles.push(thread::spawn(move || {
                for j in 0..100 {
                    q.push(i * 100 + j).unwrap();
                }
            }));
        }

        // Wait for producers
        for h in handles {
            h.join().unwrap();
        }

        // Single consumer
        let mut count = 0;
        while queue.pop().is_ok() {
            count += 1;
        }
        assert_eq!(count, 400);
    }
}
