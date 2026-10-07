//! MPSC-compatible queues backed by Crossbeam's unbounded and bounded queues.
//!
//! The safe API also permits multiple consumers. Value ownership and reclamation
//! are managed by Crossbeam rather than by unchecked raw pointers.

use crate::QueueError;
use crossbeam_queue::{ArrayQueue, SegQueue};

/// An unbounded queue usable by multiple producers and a single consumer.
pub struct MpscQueue<T> {
    inner: SegQueue<T>,
}

impl<T> MpscQueue<T> {
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

    /// Remove the oldest value.
    pub fn pop(&self) -> Result<T, QueueError> {
        self.inner.pop().ok_or(QueueError::Empty)
    }

    /// Remove a value if one is available.
    pub fn try_pop(&self) -> Option<T> {
        self.inner.pop()
    }

    /// Return an instantaneous snapshot of the queue's empty state.
    pub fn is_empty(&self) -> bool {
        self.inner.is_empty()
    }

    /// Remove up to max_items values in FIFO order.
    pub fn pop_batch(&self, max_items: usize) -> Vec<T> {
        let mut items = Vec::new();
        for _ in 0..max_items {
            match self.try_pop() {
                Some(item) => items.push(item),
                None => break,
            }
        }
        items
    }
}

impl<T> Default for MpscQueue<T> {
    fn default() -> Self {
        Self::new()
    }
}

/// A preallocated bounded queue. A zero-capacity queue is always full.
pub struct BoundedMpscQueue<T> {
    inner: Option<ArrayQueue<T>>,
}

impl<T> BoundedMpscQueue<T> {
    /// Create a queue that holds at most capacity values.
    pub fn with_capacity(capacity: usize) -> Self {
        Self {
            inner: if capacity == 0 {
                None
            } else {
                Some(ArrayQueue::new(capacity))
            },
        }
    }

    /// Enqueue a value, returning Full if capacity is exhausted.
    pub fn push(&self, item: T) -> Result<(), QueueError> {
        match &self.inner {
            Some(queue) => queue.push(item).map_err(|_| QueueError::Full),
            None => Err(QueueError::Full),
        }
    }

    /// Remove the oldest value.
    pub fn pop(&self) -> Result<T, QueueError> {
        self.inner
            .as_ref()
            .and_then(ArrayQueue::pop)
            .ok_or(QueueError::Empty)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Arc;
    use std::thread;

    #[test]
    fn test_push_pop_single_thread() {
        let queue = MpscQueue::new();

        queue.push(1).unwrap();
        queue.push(2).unwrap();
        queue.push(3).unwrap();

        assert_eq!(queue.pop().unwrap(), 1);
        assert_eq!(queue.pop().unwrap(), 2);
        assert_eq!(queue.pop().unwrap(), 3);
        assert!(matches!(queue.pop(), Err(QueueError::Empty)));
    }

    #[test]
    fn test_multi_producer_single_consumer() {
        let queue = Arc::new(MpscQueue::new());
        let num_producers = 4;
        let items_per_producer = 1000;

        // Spawn producers
        let mut handles = vec![];
        for i in 0..num_producers {
            let q = Arc::clone(&queue);
            handles.push(thread::spawn(move || {
                for j in 0..items_per_producer {
                    q.push(i * items_per_producer + j).unwrap();
                }
            }));
        }

        // Wait for all producers
        for h in handles {
            h.join().unwrap();
        }

        // Single consumer
        let mut count = 0;
        while queue.pop().is_ok() {
            count += 1;
        }

        assert_eq!(count, num_producers * items_per_producer);
    }

    #[test]
    fn test_batch_pop() {
        let queue = MpscQueue::new();

        for i in 0..100 {
            queue.push(i).unwrap();
        }

        let batch = queue.pop_batch(50);
        assert_eq!(batch.len(), 50);

        let batch = queue.pop_batch(100);
        assert_eq!(batch.len(), 50); // Only 50 remaining
    }

    #[test]
    fn test_bounded_queue() {
        let queue = BoundedMpscQueue::with_capacity(10);

        for i in 0..10 {
            queue.push(i).unwrap();
        }

        // Should be full now
        assert!(matches!(queue.push(10), Err(QueueError::Full)));

        // Pop one to make room
        queue.pop().unwrap();

        // Now we can push again
        queue.push(10).unwrap();
    }
}
