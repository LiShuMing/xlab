//! Multi-Producer Multi-Consumer Lock-free Queue
//!
//! Implementation based on the Michael-Scott queue algorithm.
//! This is the classic lock-free queue using CAS (Compare-And-Swap) operations.
//!
//! # Algorithm Overview
//!
//! ```text
//! Head -> Node1 -> Node2 -> Node3 -> Tail
//!         ↑                          ↑
//!         │                          │
//!       pop()                      push()
//! ```
//!
//! ## Push Operation
//! 1. Create new node
//! 2. CAS tail.next from null to new node
//! 3. If successful, CAS tail to new node
//! 4. If step 3 fails (another thread succeeded), help advance tail
//!
//! ## Pop Operation
//! 1. Load head pointer
//! 2. Load head.next (first real node)
//! 3. If null, queue is empty
//! 4. CAS head to head.next
//! 5. Return data from the node
//!
//! # Memory Ordering
//!
//! - `Acquire` on loads: Ensures we see all writes from other threads
//! - `Release` on stores: Ensures other threads see our writes
//! - `AcqRel` on CAS: Both acquire and release semantics

use crate::{Node, QueueError, ordering};
use std::ptr::null_mut;
use std::sync::atomic::{AtomicPtr, Ordering};

/// A lock-free multi-producer multi-consumer queue
///
/// This queue is unbounded and uses the Michael-Scott algorithm.
/// It is safe to share between multiple threads.
pub struct MpmcQueue<T> {
    /// Pointer to the dummy head node
    /// Pop operations move this forward
    head: AtomicPtr<Node<T>>,
    /// Pointer to the tail node
    /// Push operations append to this
    tail: AtomicPtr<Node<T>>,
}

impl<T> MpmcQueue<T> {
    /// Create a new empty queue
    pub fn new() -> Self {
        // Create a dummy node that head and tail both point to
        let dummy = Box::into_raw(Box::new(Node::dummy()));

        Self {
            head: AtomicPtr::new(dummy),
            tail: AtomicPtr::new(dummy),
        }
    }

    /// Push an item into the queue
    pub fn push(&self, item: T) -> Result<(), QueueError> {
        let new_node = Box::into_raw(Box::new(Node::new(item)));

        loop {
            // Load current tail
            let tail = self.tail.load(ordering::LOAD);

            // Load tail's next pointer
            let next = unsafe { (*tail).next.load(ordering::LOAD) };

            // Check if tail is still valid
            if tail != self.tail.load(ordering::LOAD) {
                continue; // Tail has changed, retry
            }

            if next.is_null() {
                // Try to link new node at the end
                match unsafe {
                    (*tail)
                        .next
                        .compare_exchange(next, new_node, ordering::RMW, ordering::LOAD)
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
                        // CAS failed, another thread succeeded
                        // Help advance tail and retry
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
    pub fn pop(&self) -> Result<T, QueueError> {
        loop {
            // Load head
            let head = self.head.load(ordering::LOAD);

            // Load tail
            let tail = self.tail.load(ordering::LOAD);

            // Load head.next (first real node)
            let next = unsafe { (*head).next.load(ordering::LOAD) };

            // Check consistency
            if head != self.head.load(ordering::LOAD) {
                continue; // Head has changed, retry
            }

            if head == tail {
                // Head equals tail, check if queue is empty
                if next.is_null() {
                    return Err(QueueError::Empty);
                }
                // Tail is lagging, help advance it
                let _ = self
                    .tail
                    .compare_exchange(tail, next, ordering::RMW, ordering::LOAD);
            } else {
                // Queue is not empty
                if next.is_null() {
                    // Race condition: queue became empty
                    return Err(QueueError::Empty);
                }

                // Try to move head forward
                match self
                    .head
                    .compare_exchange(head, next, ordering::RMW, ordering::LOAD)
                {
                    Ok(_) => {
                        // Successfully moved head
                        // Extract data from the node
                        let data = unsafe {
                            let mut node = Box::from_raw(next);
                            node.data.take().unwrap()
                        };

                        // Free the old dummy node
                        unsafe {
                            let _ = Box::from_raw(head);
                        }

                        return Ok(data);
                    }
                    Err(_) => {
                        // CAS failed, retry
                        continue;
                    }
                }
            }
        }
    }

    /// Check if the queue is empty
    pub fn is_empty(&self) -> bool {
        let head = self.head.load(ordering::LOAD);
        let tail = self.tail.load(ordering::LOAD);

        if head == tail {
            let next = unsafe { (*head).next.load(ordering::LOAD) };
            next.is_null()
        } else {
            false
        }
    }
}

impl<T> Default for MpmcQueue<T> {
    fn default() -> Self {
        Self::new()
    }
}

impl<T> Drop for MpmcQueue<T> {
    fn drop(&mut self) {
        // Pop all remaining items
        while self.pop().is_ok() {}

        // Free the remaining dummy node
        let head = self.head.load(Ordering::Relaxed);
        if !head.is_null() {
            unsafe {
                let _ = Box::from_raw(head);
            }
        }
    }
}

// SAFETY: MpmcQueue is safe to share between threads
unsafe impl<T: Send> Send for MpmcQueue<T> {}
unsafe impl<T: Send> Sync for MpmcQueue<T> {}

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
