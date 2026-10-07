//! Multi-producer multi-consumer queue with Crossbeam-managed reclamation.
//!
//! The public API retains nonblocking push/pop semantics. Crossbeam's SegQueue
//! owns queued values so no thread can access a freed dummy node.

use crate::QueueError;
use crossbeam_queue::SegQueue;

/// An unbounded, thread-safe multi-producer multi-consumer queue.
pub struct MpmcQueue<T> {
    inner: SegQueue<T>,
}

impl<T> MpmcQueue<T> {
    /// Create an empty queue.
    pub fn new() -> Self {
        Self {
            inner: SegQueue::new(),
        }
    }

    /// Enqueue one owned value.
    pub fn push(&self, item: T) -> Result<(), QueueError> {
        self.inner.push(item);
        Ok(())
    }

    /// Remove the oldest value, or report that the queue is empty.
    pub fn pop(&self) -> Result<T, QueueError> {
        self.inner.pop().ok_or(QueueError::Empty)
    }

    /// Return an instantaneous snapshot of the queue's empty state.
    pub fn is_empty(&self) -> bool {
        self.inner.is_empty()
    }
}

impl<T> Default for MpmcQueue<T> {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Arc;
    use std::thread;

    #[test]
    fn test_push_pop_single_thread() {
        let queue = MpmcQueue::new();

        assert!(queue.is_empty());
        assert!(matches!(queue.pop(), Err(QueueError::Empty)));

        queue.push(1).unwrap();
        assert!(!queue.is_empty());

        queue.push(2).unwrap();
        queue.push(3).unwrap();

        assert_eq!(queue.pop().unwrap(), 1);
        assert_eq!(queue.pop().unwrap(), 2);
        assert_eq!(queue.pop().unwrap(), 3);
        assert!(matches!(queue.pop(), Err(QueueError::Empty)));
        assert!(queue.is_empty());
    }

    #[test]
    fn test_mpmc_contention() {
        let queue = Arc::new(MpmcQueue::new());
        let num_threads = 4;
        let items_per_thread = 1000;

        // Spawn producer threads
        let mut handles = vec![];
        for i in 0..num_threads {
            let q = Arc::clone(&queue);
            handles.push(thread::spawn(move || {
                for j in 0..items_per_thread {
                    q.push(i * items_per_thread + j).unwrap();
                }
            }));
        }

        // Spawn consumer threads
        let consumer_queue = Arc::clone(&queue);
        let consumer_handle = thread::spawn(move || {
            let mut count = 0;
            let mut attempts = 0;
            while count < num_threads * items_per_thread && attempts < 100000 {
                if consumer_queue.pop().is_ok() {
                    count += 1;
                }
                attempts += 1;
            }
            count
        });

        // Wait for producers
        for h in handles {
            h.join().unwrap();
        }

        // Wait for consumer
        let consumed = consumer_handle.join().unwrap();
        assert_eq!(consumed, num_threads * items_per_thread);
    }

    #[test]
    fn test_drop_with_items() {
        let queue = MpmcQueue::new();
        queue.push(1).unwrap();
        queue.push(2).unwrap();
        queue.push(3).unwrap();
        // Queue drops here, should not leak memory
    }
}
