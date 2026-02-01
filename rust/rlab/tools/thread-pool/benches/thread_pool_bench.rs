//! Benchmarks for thread pool performance

use criterion::{black_box, criterion_group, criterion_main, Criterion};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;

/// CPU-intensive task for benchmarking
fn fibonacci(n: u32) -> u64 {
    if n <= 1 {
        return n as u64;
    }
    fibonacci(n - 1) + fibonacci(n - 2)
}

fn bench_thread_pool_vs_sequential(c: &mut Criterion) {
    let fib_values = vec![35, 36, 37, 38];

    // Sequential baseline
    c.bench_function("sequential_fib", |b| {
        b.iter(|| {
            for &n in &fib_values {
                black_box(fibonacci(n));
            }
        });
    });

    // Thread pool with different sizes
    for num_threads in [2, 4, 8] {
        let pool = thread_pool::ThreadPool::new(num_threads).unwrap();
        let name = format!("pool_{}threads_fib", num_threads);

        c.bench_function(&name, |b| {
            b.iter(|| {
                let counter = Arc::new(AtomicUsize::new(0));
                for &n in &fib_values {
                    let counter = Arc::clone(&counter);
                    pool.execute(move || {
                        black_box(fibonacci(n));
                        counter.fetch_add(1, Ordering::SeqCst);
                    })
                    .unwrap();
                }
                // Wait for completion
                while counter.load(Ordering::SeqCst) < fib_values.len() {
                    std::thread::sleep(std::time::Duration::from_micros(100));
                }
            });
        });
    }
}

fn bench_task_overhead(c: &mut Criterion) {
    let pool = thread_pool::ThreadPool::new(4).unwrap();

    // Benchmark task submission overhead
    c.bench_function("task_submission_overhead", |b| {
        b.iter(|| {
            pool.execute(|| {
                // Minimal work
                black_box(42);
            })
            .unwrap();
        });
    });

    // Benchmark small work items (high overhead ratio)
    c.bench_function("small_tasks_100", |b| {
        b.iter(|| {
            let counter = Arc::new(AtomicUsize::new(0));
            for i in 0..100 {
                let counter = Arc::clone(&counter);
                pool.execute(move || {
                    black_box(i * i);
                    counter.fetch_add(1, Ordering::SeqCst);
                })
                .unwrap();
            }
            while counter.load(Ordering::SeqCst) < 100 {
                std::thread::yield_now();
            }
        });
    });
}

fn bench_throughput(c: &mut Criterion) {
    let mut group = c.benchmark_group("throughput");

    for num_threads in [1, 2, 4, 8] {
        let pool = thread_pool::ThreadPool::new(num_threads).unwrap();
        let name = format!("tasks_per_sec_{}threads", num_threads);

        group.throughput(criterion::Throughput::Elements(1000));
        group.bench_function(name, |b| {
            b.iter(|| {
                let counter = Arc::new(AtomicUsize::new(0));
                for i in 0..1000 {
                    let counter = Arc::clone(&counter);
                    pool.execute(move || {
                        // Simulate moderate work
                        let mut sum = 0u64;
                        for j in 0..100 {
                            sum = sum.wrapping_add(black_box(i * j) as u64);
                        }
                        counter.fetch_add(1, Ordering::SeqCst);
                    })
                    .unwrap();
                }
                while counter.load(Ordering::SeqCst) < 1000 {
                    std::thread::yield_now();
                }
            });
        });
    }

    group.finish();
}

criterion_group!(
    benches,
    bench_thread_pool_vs_sequential,
    bench_task_overhead,
    bench_throughput
);
criterion_main!(benches);
