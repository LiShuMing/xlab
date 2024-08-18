//! Compare different queue implementations
//!
//! This example compares the performance of our lock-free queues
//! against std::sync::mpsc channels.

use std::sync::mpsc;
use std::sync::Arc;
use std::thread;
use std::time::{Duration, Instant};

fn benchmark_std_mpsc(num_producers: usize, items_per_producer: usize) -> Duration {
    let (tx, rx) = mpsc::channel();

    let start = Instant::now();

    // Producers
    let mut handles = vec![];
    for i in 0..num_producers {
        let tx = tx.clone();
        handles.push(thread::spawn(move || {
            let start_item = i * items_per_producer;
            for j in 0..items_per_producer {
                tx.send((start_item + j) as i32).unwrap();
            }
        }));
    }

    // Drop original sender so channel closes when all producers done
    drop(tx);

    // Consumer
    let consumer = thread::spawn(move || {
        let mut count = 0;
        while rx.recv().is_ok() {
            count += 1;
        }
        count
    });

    for h in handles {
        h.join().unwrap();
    }

    let consumed = consumer.join().unwrap();
    let elapsed = start.elapsed();

    assert_eq!(consumed, num_producers * items_per_producer);
    elapsed
}

fn benchmark_mpmc(num_producers: usize, items_per_producer: usize) -> Duration {
    let queue = Arc::new(lockfree_queue::MpmcQueue::<i32>::new());

    let start = Instant::now();

    // Producers
    let mut handles = vec![];
    for i in 0..num_producers {
        let q = Arc::clone(&queue);
        handles.push(thread::spawn(move || {
            let start_item = i * items_per_producer;
            for j in 0..items_per_producer {
                q.push((start_item + j) as i32).unwrap();
            }
        }));
    }

    // Consumer
    let q = Arc::clone(&queue);
    let consumer = thread::spawn(move || {
        let mut count = 0;
        while count < num_producers * items_per_producer {
            if q.pop().is_ok() {
                count += 1;
            }
        }
        count
    });

    for h in handles {
        h.join().unwrap();
    }

    let consumed = consumer.join().unwrap();
    let elapsed = start.elapsed();

    assert_eq!(consumed, num_producers * items_per_producer);
    elapsed
}

fn benchmark_mpsc(num_producers: usize, items_per_producer: usize) -> Duration {
    let queue = Arc::new(lockfree_queue::MpscQueue::<i32>::new());

    let start = Instant::now();

    // Producers
    let mut handles = vec![];
    for i in 0..num_producers {
        let q = Arc::clone(&queue);
        handles.push(thread::spawn(move || {
            let start_item = i * items_per_producer;
            for j in 0..items_per_producer {
                q.push((start_item + j) as i32).unwrap();
            }
        }));
    }

    // Consumer
    let q = Arc::clone(&queue);
    let consumer = thread::spawn(move || {
        let mut count = 0;
        while count < num_producers * items_per_producer {
            if q.pop().is_ok() {
                count += 1;
            }
        }
        count
    });

    for h in handles {
        h.join().unwrap();
    }

    let consumed = consumer.join().unwrap();
    let elapsed = start.elapsed();

    assert_eq!(consumed, num_producers * items_per_producer);
    elapsed
}

fn main() {
    println!("=== Queue Performance Comparison ===\n");

    let configs = vec![
        (1, 100_000, "Single Producer"),
        (2, 100_000, "Two Producers"),
        (4, 100_000, "Four Producers"),
    ];

    for (num_producers, items_per_producer, description) in configs {
        println!(
            "--- {} ({} items total) ---",
            description,
            num_producers * items_per_producer
        );

        // Run multiple times for better accuracy
        let runs = 5;

        let std_time: Duration = (0..runs)
            .map(|_| benchmark_std_mpsc(num_producers, items_per_producer))
            .sum::<Duration>()
            / runs;

        let mpmc_time: Duration = (0..runs)
            .map(|_| benchmark_mpmc(num_producers, items_per_producer))
            .sum::<Duration>()
            / runs;

        let mpsc_time: Duration = (0..runs)
            .map(|_| benchmark_mpsc(num_producers, items_per_producer))
            .sum::<Duration>()
            / runs;

        let std_ops = (num_producers * items_per_producer) as f64 / std_time.as_secs_f64();
        let mpmc_ops = (num_producers * items_per_producer) as f64 / mpmc_time.as_secs_f64();
        let mpsc_ops = (num_producers * items_per_producer) as f64 / mpsc_time.as_secs_f64();

        println!("  std::sync::mpsc: {:?} ({:.0} ops/sec)", std_time, std_ops);
        println!(
            "  MPMC (lockfree): {:?} ({:.0} ops/sec)",
            mpmc_time, mpmc_ops
        );
        println!(
            "  MPSC (lockfree): {:?} ({:.0} ops/sec)",
            mpsc_time, mpsc_ops
        );

        println!();
    }

    println!("Notes:");
    println!(
        "  - std::sync::mpsc is optimized for Rust and may use platform-specific optimizations"
    );
    println!("  - Our lock-free queues are educational implementations");
    println!("  - MPSC is optimized for single consumer and should be faster than MPMC");
}
