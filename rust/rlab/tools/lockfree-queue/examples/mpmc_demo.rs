//! MPMC Queue Demo
//!
//! Demonstrates the Multi-Producer Multi-Consumer lock-free queue
//! with concurrent producers and consumers.

use std::sync::Arc;
use std::thread;
use std::time::{Duration, Instant};

fn main() {
    println!("=== MPMC Queue Demo ===\n");

    let queue = Arc::new(lockfree_queue::MpmcQueue::<i32>::new());

    let num_producers = 2;
    let num_consumers = 2;
    let items_per_producer = 10000;

    println!("Configuration:");
    println!("  Producers: {}", num_producers);
    println!("  Consumers: {}", num_consumers);
    println!("  Items per producer: {}", items_per_producer);
    println!("  Total items: {}\n", num_producers * items_per_producer);

    let start = Instant::now();

    // Spawn producers
    let mut producer_handles = vec![];
    for i in 0..num_producers {
        let q = Arc::clone(&queue);
        let handle = thread::spawn(move || {
            let start_item = i * items_per_producer;
            for j in 0..items_per_producer {
                q.push((start_item + j) as i32).unwrap();
            }
        });
        producer_handles.push(handle);
    }

    // Spawn consumers
    let mut consumer_handles = vec![];
    for _ in 0..num_consumers {
        let q = Arc::clone(&queue);
        let handle = thread::spawn(move || {
            let mut count = 0;
            let mut empty_count = 0;

            while count < items_per_producer * num_producers / num_consumers {
                match q.pop() {
                    Ok(_) => count += 1,
                    Err(_) => {
                        empty_count += 1;
                        if empty_count > 1000 {
                            thread::yield_now();
                        }
                    }
                }
            }
            count
        });
        consumer_handles.push(handle);
    }

    // Wait for producers
    for h in producer_handles {
        h.join().unwrap();
    }
    let producer_done = Instant::now();
    println!("All producers done in {:?}", producer_done - start);

    // Wait for consumers
    let mut total_consumed = 0;
    for h in consumer_handles {
        total_consumed += h.join().unwrap();
    }
    let consumer_done = Instant::now();
    println!("All consumers done in {:?}", consumer_done - producer_done);
    println!("\nTotal items consumed: {}", total_consumed);
    println!("Total time: {:?}", consumer_done - start);

    // Calculate throughput
    let throughput =
        (num_producers * items_per_producer) as f64 / (consumer_done - start).as_secs_f64();
    println!("Throughput: {:.0} ops/sec", throughput);

    // Verify queue is empty
    assert!(queue.is_empty());
    println!("\n✓ Queue is empty after test");
}
