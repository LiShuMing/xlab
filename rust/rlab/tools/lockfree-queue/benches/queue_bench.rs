//! Benchmarks for lock-free queues

use criterion::{black_box, criterion_group, criterion_main, Criterion, Throughput};
use std::sync::Arc;
use std::thread;

fn bench_mpmc_single_thread(c: &mut Criterion) {
    let mut group = c.benchmark_group("mpmc_single_thread");

    group.bench_function("push", |b| {
        let queue = lockfree_queue::MpmcQueue::<i32>::new();
        b.iter(|| {
            queue.push(black_box(42)).unwrap();
        });
    });

    group.bench_function("push_pop", |b| {
        let queue = lockfree_queue::MpmcQueue::<i32>::new();
        b.iter(|| {
            queue.push(black_box(42)).unwrap();
            black_box(queue.pop().unwrap());
        });
    });

    group.finish();
}

fn bench_mpmc_multi_thread(c: &mut Criterion) {
    let mut group = c.benchmark_group("mpmc_multi_thread");
    group.throughput(Throughput::Elements(10000));

    group.bench_function("2_producers", |b| {
        b.iter(|| {
            let queue = Arc::new(lockfree_queue::MpmcQueue::<i32>::new());

            let q1 = Arc::clone(&queue);
            let p1 = thread::spawn(move || {
                for i in 0..5000 {
                    q1.push(i as i32).unwrap();
                }
            });

            let q2 = Arc::clone(&queue);
            let p2 = thread::spawn(move || {
                for i in 0..5000 {
                    q2.push(i as i32).unwrap();
                }
            });

            let consumer = thread::spawn(move || {
                let mut count = 0;
                while count < 10000 {
                    if queue.pop().is_ok() {
                        count += 1;
                    }
                }
            });

            p1.join().unwrap();
            p2.join().unwrap();
            consumer.join().unwrap();
        });
    });

    group.finish();
}

fn bench_mpsc_multi_thread(c: &mut Criterion) {
    let mut group = c.benchmark_group("mpsc_multi_thread");
    group.throughput(Throughput::Elements(10000));

    group.bench_function("2_producers", |b| {
        b.iter(|| {
            let queue = Arc::new(lockfree_queue::MpscQueue::<i32>::new());

            let q1 = Arc::clone(&queue);
            let p1 = thread::spawn(move || {
                for i in 0..5000 {
                    q1.push(i as i32).unwrap();
                }
            });

            let q2 = Arc::clone(&queue);
            let p2 = thread::spawn(move || {
                for i in 0..5000 {
                    q2.push(i as i32).unwrap();
                }
            });

            let consumer = thread::spawn(move || {
                let mut count = 0;
                while count < 10000 {
                    if queue.pop().is_ok() {
                        count += 1;
                    }
                }
            });

            p1.join().unwrap();
            p2.join().unwrap();
            consumer.join().unwrap();
        });
    });

    group.finish();
}

fn bench_std_mpsc(c: &mut Criterion) {
    use std::sync::mpsc;

    let mut group = c.benchmark_group("std_mpsc");
    group.throughput(Throughput::Elements(10000));

    group.bench_function("2_producers", |b| {
        b.iter(|| {
            let (tx, rx) = mpsc::channel();

            let tx1 = tx.clone();
            let p1 = thread::spawn(move || {
                for i in 0..5000 {
                    tx1.send(i as i32).unwrap();
                }
            });

            let tx2 = tx.clone();
            let p2 = thread::spawn(move || {
                for i in 0..5000 {
                    tx2.send(i as i32).unwrap();
                }
            });

            drop(tx);

            let consumer = thread::spawn(move || {
                let mut count = 0;
                while rx.recv().is_ok() {
                    count += 1;
                }
                count
            });

            p1.join().unwrap();
            p2.join().unwrap();
            consumer.join().unwrap();
        });
    });

    group.finish();
}

criterion_group!(
    benches,
    bench_mpmc_single_thread,
    bench_mpmc_multi_thread,
    bench_mpsc_multi_thread,
    bench_std_mpsc
);
criterion_main!(benches);
