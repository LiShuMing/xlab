//! Performance comparison example
//!
//! This example demonstrates:
//! - The overhead of thread pool vs sequential execution
//! - The benefit of parallelism for CPU-intensive tasks
//! - Common pitfalls and performance issues

use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;
use std::time::{Duration, Instant};

/// CPU-intensive computation: Calculate nth Fibonacci number recursively
fn fibonacci(n: u32) -> u64 {
    if n <= 1 {
        return n as u64;
    }
    fibonacci(n - 1) + fibonacci(n - 2)
}

fn main() {
    println!("Thread Pool - Performance Analysis\n");

    // Test parameters
    let fib_values = vec![35, 36, 37, 38, 35, 36, 37, 38];
    let num_threads = num_cpus::get();

    println!("System has {} CPUs", num_threads);
    println!("Computing fibonacci for {:?}\n", fib_values);

    // Sequential execution
    println!("--- Sequential Execution ---");
    let start = Instant::now();
    let seq_results: Vec<u64> = fib_values.iter().map(|&n| fibonacci(n)).collect();
    let seq_duration = start.elapsed();
    println!("Results: {:?}", seq_results);
    println!("Time: {:?}\n", seq_duration);

    // Thread pool execution
    println!("--- Thread Pool Execution ({} threads) ---", num_threads);
    let pool = thread_pool::ThreadPool::new(num_threads).expect("Failed to create pool");

    let start = Instant::now();
    let counter = Arc::new(AtomicUsize::new(0));

    for &n in &fib_values {
        let counter = Arc::clone(&counter);
        pool.execute(move || {
            let result = fibonacci(n);
            let idx = counter.fetch_add(1, Ordering::SeqCst);
            println!("fib({}) = {} (task {})", n, result, idx);
        })
        .expect("Failed to execute task");
    }

    // Wait for all tasks to complete
    while counter.load(Ordering::SeqCst) < fib_values.len() {
        std::thread::sleep(Duration::from_millis(10));
    }
    let pool_duration = start.elapsed();
    println!("Time: {:?}\n", pool_duration);

    // Speedup calculation
    let speedup = seq_duration.as_secs_f64() / pool_duration.as_secs_f64();
    println!("--- Summary ---");
    println!("Sequential: {:?}", seq_duration);
    println!("Thread Pool: {:?}", pool_duration);
    println!("Speedup: {:.2}x", speedup);

    // Demonstrate: Not all tasks benefit from parallelism
    println!("\n--- Demonstrating Overhead ---");
    let small_tasks: Vec<u32> = (0..1000).collect();

    // Sequential: Very fast for small tasks
    let start = Instant::now();
    let _: Vec<u32> = small_tasks.iter().map(|&n| n * n).collect();
    let small_seq = start.elapsed();
    println!("Small tasks (sequential): {:?}", small_seq);

    // Thread pool: Overhead may exceed benefit
    let counter = Arc::new(AtomicUsize::new(0));
    let start = Instant::now();
    for &n in &small_tasks {
        let counter = Arc::clone(&counter);
        pool.execute(move || {
            let _ = n * n;
            counter.fetch_add(1, Ordering::SeqCst);
        })
        .unwrap();
    }
    while counter.load(Ordering::SeqCst) < small_tasks.len() {
        std::thread::sleep(Duration::from_micros(100));
    }
    let small_pool = start.elapsed();
    println!("Small tasks (thread pool): {:?}", small_pool);

    if small_pool > small_seq {
        println!("⚠️  Thread pool overhead exceeded benefit for small tasks!");
    }

    pool.shutdown();
    println!("\nDone!");
}
