//! Async/await tests using Tokio
//!
//! These tests demonstrate:
//! - Async functions
//! - Spawning tasks
//! - Joining async tasks
//! - Runtime configuration

use tokio::task;
use tokio::time::{sleep, Duration};

#[tokio::test]
async fn test_basic_async() {
    let join = task::spawn(async {
        "hello world!"
    });
    
    let result = join.await.unwrap();
    assert_eq!(result, "hello world!");
}

#[tokio::test]
async fn test_async_with_computation() {
    let join = task::spawn(async {
        let mut sum = 0;
        for i in 1..=100 {
            sum += i;
        }
        sum
    });
    
    let result = join.await.unwrap();
    assert_eq!(result, 5050);
}

#[tokio::test]
async fn test_async_sleep() {
    let start = tokio::time::Instant::now();
    
    sleep(Duration::from_millis(10)).await;
    
    let elapsed = start.elapsed();
    assert!(elapsed >= Duration::from_millis(10));
}

#[tokio::test]
async fn test_concurrent_tasks() {
    let mut handles = vec![];
    
    for i in 0..5 {
        handles.push(task::spawn(async move {
            sleep(Duration::from_millis(10)).await;
            i * i
        }));
    }
    
    let mut results = vec![];
    for handle in handles {
        results.push(handle.await.unwrap());
    }
    
    assert_eq!(results, vec![0, 1, 4, 9, 16]);
}

#[tokio::test]
async fn test_async_closure_capture() {
    let data = vec![1, 2, 3, 4, 5];
    
    let join = task::spawn(async move {
        data.iter().sum::<i32>()
    });
    
    let result = join.await.unwrap();
    assert_eq!(result, 15);
}

#[test]
fn test_runtime_creation() {
    // Manual runtime creation for sync contexts
    let rt = tokio::runtime::Runtime::new().unwrap();
    
    let result = rt.block_on(async {
        let join = tokio::spawn(async { 42 });
        join.await.unwrap()
    });
    
    assert_eq!(result, 42);
}

#[test]
fn test_current_thread_runtime() {
    // Single-threaded runtime
    let rt = tokio::runtime::Builder::new_current_thread()
        .build()
        .unwrap();
    
    let result = rt.block_on(async {
        let value = async { 10 }.await;
        value * 2
    });
    
    assert_eq!(result, 20);
}

#[tokio::test]
async fn test_select() {
    use tokio::select;
    
    let result = select! {
        _ = sleep(Duration::from_millis(50)) => "timeout",
        _ = sleep(Duration::from_millis(100)) => "late",
    };
    
    assert_eq!(result, "timeout");
}
