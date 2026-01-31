//! Concurrency tests
//!
//! These tests demonstrate Rust's concurrency primitives:
//! - Threads and spawning
//! - Join handles
//! - Move closures with threads

use std::thread;
use std::sync::mpsc;
use std::time::Duration;

#[test]
fn test_basic_thread() {
    let handle = thread::spawn(|| {
        "hello from thread"
    });
    
    let result = handle.join().unwrap();
    assert_eq!(result, "hello from thread");
}

#[test]
fn test_thread_with_move() {
    let v = vec![1, 2, 3];
    
    let handle = thread::spawn(move || {
        let sum: i32 = v.iter().sum();
        sum
    });
    
    let result = handle.join().unwrap();
    assert_eq!(result, 6);
    // v is moved into the thread, can't use it here
}

#[test]
fn test_multiple_threads() {
    let mut handles = vec![];
    
    for i in 0..5 {
        handles.push(thread::spawn(move || {
            i * i
        }));
    }
    
    let results: Vec<i32> = handles
        .into_iter()
        .map(|h| h.join().unwrap())
        .collect();
    
    assert_eq!(results, vec![0, 1, 4, 9, 16]);
}

#[test]
fn test_channel_communication() {
    let (tx, rx) = mpsc::channel();
    
    thread::spawn(move || {
        tx.send("hello").unwrap();
    });
    
    let received = rx.recv().unwrap();
    assert_eq!(received, "hello");
}

#[test]
fn test_channel_multiple_messages() {
    let (tx, rx) = mpsc::channel();
    
    thread::spawn(move || {
        for i in 0..5 {
            tx.send(i).unwrap();
        }
    });
    
    let mut received = vec![];
    for _ in 0..5 {
        received.push(rx.recv().unwrap());
    }
    
    assert_eq!(received, vec![0, 1, 2, 3, 4]);
}

#[test]
fn test_thread_sleep() {
    let start = std::time::Instant::now();
    
    thread::sleep(Duration::from_millis(10));
    
    let elapsed = start.elapsed();
    assert!(elapsed >= Duration::from_millis(10));
}

#[test]
fn test_thread_builder() {
    let handle = thread::Builder::new()
        .name("test_thread".to_string())
        .spawn(|| {
            thread::current().name().unwrap().to_string()
        })
        .unwrap();
    
    let name = handle.join().unwrap();
    assert_eq!(name, "test_thread");
}
