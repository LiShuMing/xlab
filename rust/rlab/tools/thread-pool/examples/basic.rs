//! Basic usage example of the thread pool

use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;
use std::time::Duration;

fn main() {
    println!("Thread Pool - Basic Example\n");

    // Create a thread pool with 4 workers
    let pool = thread_pool::ThreadPool::new(4).expect("Failed to create thread pool");

    let task_count = 20;
    let counter = Arc::new(AtomicUsize::new(0));

    println!("Submitting {} tasks to the pool...", task_count);

    // Submit tasks to the pool
    for i in 0..task_count {
        let counter = Arc::clone(&counter);
        pool.execute(move || {
            // Simulate some work
            std::thread::sleep(Duration::from_millis(50));
            let count = counter.fetch_add(1, Ordering::SeqCst) + 1;
            println!("Task {} completed (total completed: {})", i, count);
        })
        .expect("Failed to execute task");
    }

    println!("All tasks submitted. Waiting for completion...\n");

    // Give time for tasks to complete
    std::thread::sleep(Duration::from_millis(500));

    let final_count = counter.load(Ordering::SeqCst);
    println!("\nCompleted {} out of {} tasks", final_count, task_count);

    // Graceful shutdown
    println!("Shutting down thread pool...");
    pool.shutdown();
    println!("Thread pool shut down successfully");
}
