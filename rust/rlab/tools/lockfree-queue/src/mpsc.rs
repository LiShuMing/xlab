//! Multi-Producer Single-Consumer Lock-free Queue
//!
//! This is an optimized version for the single-consumer case.
//! Since there's only one consumer, we can use a simpler algorithm
//! that doesn't need to CAS on the head pointer.
//!
//! # Algorithm Overview
//!
//! ```text
//! Producers -> [lock-free push] -> Queue -> [single consumer pop] -> Consumer
//! ```
//!
//! ## Key Optimizations for SPSC/MPSC
//!
//! 1. **Consumer doesn't need CAS**: Since there's only one consumer,
//!    we can use simple loads/stores for the head pointer.
//!
//! 2. **Separate head cache**: The consumer can cache the head pointer
//!    locally without atomics.
//!
//! 3. **Batch processing**: Consumer can process multiple items
//!    before updating the shared state.
//!
//! # Memory Ordering
//!
//! - **Producer (push)**: `Release` store to make data visible
//! - **Consumer (pop)**: `Acquire` load to see producer's data
//! - **Tail update**: `AcqRel` CAS for coordination

use crate::{ordering, Node, QueueError};
use std::cell::UnsafeCell;
use std::ptr::null_mut;
use std::sync::atomic::{AtomicPtr, AtomicUsize, Ordering};

/// A lock-free multi-producer single-consumer queue
///
/// This queue is optimized for the case where there is only one
/// thread consuming from the queue. Multiple threads can push
/// concurrently.
///
/// # Safety
///
/// It is undefined behavior to call `pop()` from multiple threads
/// concurrently. The queue does not enforce this at runtime.
pub struct MpscQueue<T> {
    /// Pointer to the dummy head node
    /// Only the consumer modifies this
    head: UnsafeCell<*mut Node<T>>,

    /// Pointer to the tail node
    /// Multiple producers CAS this
    tail: AtomicPtr<Node<T>>,

    /// Cached head for the consumer
    /// This avoids atomic operations on the consumer side
    consumer_cache: UnsafeCell<*mut Node<T>>,
}

// SAFETY: MpscQueue is safe to share between threads for push operations
// The pop operation requires single-threaded access
unsafe impl<T: Send> Send for MpscQueue<T> {}
unsafe impl<T: Send> Sync for MpscQueue<T> {}

impl<T> MpscQueue<T> {
    /// Create a new empty MPSC queue
    ///
    /// # Example
    ///
    /// ```
    /// use lockfree_queue::MpscQueue;
    ///
    /// let queue = MpscQueue::<i32>::new();
    /// queue.push(42).unwrap();
    /// ```
    pub fn new() -> Self {
        let dummy = Box::into_raw(Box::new(Node::dummy()));

        Self {
            head: UnsafeCell::new(dummy),
            tail: AtomicPtr::new(dummy),
            consumer_cache: UnsafeCell::new(dummy),
        }
    }

    /// Push an item into the queue
    ///
    /// This operation is lock-free and thread-safe.
    /// Multiple threads can call push concurrently.
    ///
    /// # Algorithm
    ///
    /// 1. Allocate new node
    /// 2. CAS tail.next to point to new node
    /// 3. CAS tail to new node
    pub fn push(&self, item: T) -> Result<(), QueueError> {
        let new_node = Box::into_raw(Box::new(Node::new(item)));

        loop {
            // Load current tail
            let tail = self.tail.load(ordering::LOAD);

            // Load tail's next
            let next = unsafe { (*tail).next.load(ordering::LOAD) };

            // Verify tail is still valid
            if tail != self.tail.load(ordering::LOAD) {
                continue;
            }

            if next.is_null() {
                // Try to link new node
                match unsafe {
                    (*tail).next.compare_exchange(
                        null_mut(),
                        new_node,
                        ordering::RMW,
                        ordering::LOAD,
                    )
                } {
                    Ok(_) => {
                        // Successfully linked, try to advance tail
                        let _ = self.tail.compare_exchange(
                            tail,
                            new_node,
                            ordering::RMW,
                            ordering::LOAD,
                        );
                        return Ok(());
                    }
                    Err(_) => {
                        // Another thread succeeded, help advance tail
                        let actual_next = unsafe { (*tail).next.load(ordering::LOAD) };
                        if !actual_next.is_null() {
                            let _ = self.tail.compare_exchange(
                                tail,
                                actual_next,
                                ordering::RMW,
                                ordering::LOAD,
                            );
                        }
                    }
                }
            } else {
                // Tail is lagging, help advance it
                let _ = self
                    .tail
                    .compare_exchange(tail, next, ordering::RMW, ordering::LOAD);
            }
        }
    }

    /// Pop an item from the queue
    ///
    /// # Safety
    ///
    /// This method must only be called from a single thread.
    /// Calling pop from multiple threads concurrently is undefined behavior.
    ///
    /// # Algorithm
    ///
    /// 1. Check cached head's next
    /// 2. If exists, advance cached head and return data
    /// 3. Otherwise, check tail and retry
    pub fn pop(&self) -> Result<T, QueueError> {
        unsafe {
            // Get cached head
            let cached_head = *self.consumer_cache.get();

            // Check if there's a next node
            let next = (*cached_head).next.load(ordering::LOAD);

            if !next.is_null() {
                // We have a node to return
                let data = {
                    let mut node = Box::from_raw(next);
                    node.data.take().unwrap()
                };

                // Update cached head
                *self.consumer_cache.get() = next;

                // Update shared head (deferred cleanup)
                // In a real implementation, we might batch this
                *self.head.get() = next;

                // Free old dummy node
                let _ = Box::from_raw(cached_head);

                return Ok(data);
            }

            // Check if queue is truly empty
            let tail = self.tail.load(ordering::LOAD);
            if cached_head == tail {
                return Err(QueueError::Empty);
            }

            // Tail is lagging, wait a bit and retry
            // In practice, we might want to help advance the tail
            Err(QueueError::Empty)
        }
    }

    /// Try to pop an item without blocking
    ///
    /// This is a convenience method that doesn't require unsafe
    /// because we assume single-threaded usage.
    pub fn try_pop(&self) -> Option<T> {
        self.pop().ok()
    }

    /// Check if the queue is empty
    ///
    /// Note: This is a best-effort check for the consumer thread.
    pub fn is_empty(&self) -> bool {
        unsafe {
            let cached_head = *self.consumer_cache.get();
            let next = (*cached_head).next.load(ordering::LOAD);
            next.is_null()
        }
    }

    /// Batch pop multiple items
    ///
    /// This is more efficient than popping one by one
    /// because it reduces the number of memory allocations freed.
    ///
    /// # Safety
    ///
    /// Must only be called from the consumer thread.
    pub fn pop_batch(&self, max_items: usize) -> Vec<T> {
        let mut items = Vec::with_capacity(max_items);

        for _ in 0..max_items {
            match self.pop() {
                Ok(item) => items.push(item),
                Err(_) => break,
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

impl<T> Drop for MpscQueue<T> {
    fn drop(&mut self) {
        // Pop all remaining items
        while self.pop().is_ok() {}

        // Free remaining nodes
        unsafe {
            let head = *self.head.get();
            if !head.is_null() {
                let _ = Box::from_raw(head);
            }

            // Note: consumer_cache points to the same node as head
            // or a more recent one, so we don't need to free it separately
        }
    }
}

/// A bounded MPSC queue with pre-allocated buffer
///
/// This is useful when you want to avoid dynamic allocations
/// during push operations.
pub struct BoundedMpscQueue<T> {
    inner: MpscQueue<T>,
    capacity: AtomicUsize,
    current_size: AtomicUsize,
}

impl<T> BoundedMpscQueue<T> {
    /// Create a new bounded queue
    ///
    /// Note: This is a simplified implementation. A real bounded
    /// queue would need a ring buffer or similar structure.
    pub fn with_capacity(_capacity: usize) -> Self {
        Self {
            inner: MpscQueue::new(),
            capacity: AtomicUsize::new(_capacity),
            current_size: AtomicUsize::new(0),
        }
    }

    /// Push an item, failing if queue is full
    pub fn push(&self, item: T) -> Result<(), QueueError> {
        // Check capacity
        let size = self.current_size.fetch_add(1, Ordering::AcqRel);
        let capacity = self.capacity.load(Ordering::Acquire);

        if size >= capacity {
            self.current_size.fetch_sub(1, Ordering::Relaxed);
            return Err(QueueError::Full);
        }

        self.inner.push(item)
    }

    /// Pop an item
    pub fn pop(&self) -> Result<T, QueueError> {
        let result = self.inner.pop();
        if result.is_ok() {
            self.current_size.fetch_sub(1, Ordering::Relaxed);
        }
        result
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
