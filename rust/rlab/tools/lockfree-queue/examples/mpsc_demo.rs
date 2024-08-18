//! MPSC Queue Demo
//!
//! Demonstrates the Multi-Producer Single-Consumer lock-free queue.
//! This is optimized for the case where there's only one consumer.

use std::sync::Arc;
use std::thread;
use std::time::{Duration, Instant};

fn main() {
    println!("=== MPSC Queue Demo ===\n");

    let queue = Arc::new(lockfree_queue::MpscQueue::<i32>::new());

    let num_producers = 4;
    let items_per_producer = 10000;

    println!("Configuration:");
    println!("  Producers: {}", num_producers);
    println!("  Consumers: 1 (single consumer)");
    println!("  Items per producer: {}", items_per_producer);
    println!("  Total items: {}\n", num_producers * items_per_producer);

    let start = Instant::now();

    // Spawn producers
    let mut handles = vec![];
    for i in 0..num_producers {
        let q = Arc::clone(&queue);
        let handle = thread::spawn(move || {
            let start_item = i * items_per_producer;
            for j in 0..items_per_producer {
                q.push((start_item + j) as i32).unwrap();
            }
        });
        handles.push(handle);
    }

    // Single consumer
    let q = Arc::clone(&queue);
    let consumer_start = Instant::now();
    let consumer_handle = thread::spawn(move || {
        let mut count = 0;
        let mut empty_count = 0;
        let mut batch_count = 0;

        // Use batch pop for efficiency
        while count < num_producers * items_per_producer {
            // Try batch pop first
            let batch = q.pop_batch(100);
            if !batch.is_empty() {
                count += batch.len();
                batch_count += 1;
                empty_count = 0;
            } else {
                empty_count += 1;
                if empty_count > 100 {
                    thread::yield_now();
                }
            }
        }

        println!("Consumer used {} batch operations", batch_count);
        count
    });

    // Wait for producers
    for h in handles {
        h.join().unwrap();
    }
    let producer_done = Instant::now();
    println!("All producers done in {:?}", producer_done - start);

    // Wait for consumer
    let consumed = consumer_handle.join().unwrap();
    let consumer_done = Instant::now();
    println!("Consumer done in {:?}", consumer_done - producer_done);

    println!("\nTotal items consumed: {}", consumed);
    println!("Total time: {:?}", consumer_done - start);

    let throughput =
        (num_producers * items_per_producer) as f64 / (consumer_done - start).as_secs_f64();
    println!("Throughput: {:.0} ops/sec", throughput);

    assert!(queue.is_empty());
    println!("\n✓ Queue is empty after test");
}
