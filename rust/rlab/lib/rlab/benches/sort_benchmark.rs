//! Criterion benchmarks for sorting algorithms
//!
//! Run with: cargo bench

use criterion::{black_box, criterion_group, criterion_main, Criterion, BenchmarkId};
use rlab::sort::*;

fn generate_random_data(size: usize) -> Vec<i32> {
    use fastrand::Rng;
    let mut rng = Rng::new();
    (0..size).map(|_| rng.i32(0..1_000_000)).collect()
}

fn generate_sorted_data(size: usize) -> Vec<i32> {
    (0..size as i32).collect()
}

fn generate_reverse_data(size: usize) -> Vec<i32> {
    (0..size as i32).rev().collect()
}

fn bench_comparison_sorts(c: &mut Criterion) {
    let mut group = c.benchmark_group("comparison_sorts_random");
    
    for size in [100, 1000, 10000].iter() {
        group.bench_with_input(BenchmarkId::new("quick_sort", size), size, |b, &size| {
            let data = generate_random_data(size);
            b.iter(|| {
                let mut arr = data.clone();
                quick_sort(black_box(&mut arr));
            });
        });
        
        group.bench_with_input(BenchmarkId::new("merge_sort", size), size, |b, &size| {
            let data = generate_random_data(size);
            b.iter(|| {
                let mut arr = data.clone();
                merge_sort(black_box(&mut arr));
            });
        });
        
        group.bench_with_input(BenchmarkId::new("heap_sort", size), size, |b, &size| {
            let data = generate_random_data(size);
            b.iter(|| {
                let mut arr = data.clone();
                heap_sort(black_box(&mut arr));
            });
        });
        
        group.bench_with_input(BenchmarkId::new("tim_sort", size), size, |b, &size| {
            let data = generate_random_data(size);
            b.iter(|| {
                let mut arr = data.clone();
                tim_sort(black_box(&mut arr));
            });
        });
        
        group.bench_with_input(BenchmarkId::new("intro_sort", size), size, |b, &size| {
            let data = generate_random_data(size);
            b.iter(|| {
                let mut arr = data.clone();
                intro_sort(black_box(&mut arr));
            });
        });
    }
    
    group.finish();
}

fn bench_simple_sorts(c: &mut Criterion) {
    let mut group = c.benchmark_group("simple_sorts");
    
    // Only test on small sizes for O(n²) algorithms
    for size in [10, 50, 100].iter() {
        group.bench_with_input(BenchmarkId::new("insertion_sort", size), size, |b, &size| {
            let data = generate_random_data(size);
            b.iter(|| {
                let mut arr = data.clone();
                insertion_sort(black_box(&mut arr));
            });
        });
        
        group.bench_with_input(BenchmarkId::new("shell_sort", size), size, |b, &size| {
            let data = generate_random_data(size);
            b.iter(|| {
                let mut arr = data.clone();
                shell_sort(black_box(&mut arr));
            });
        });
    }
    
    group.finish();
}

fn bench_integer_sorts(c: &mut Criterion) {
    let mut group = c.benchmark_group("integer_sorts");
    
    for size in [1000, 10000, 100000].iter() {
        group.bench_with_input(BenchmarkId::new("radix_sort_lsd", size), size, |b, &size| {
            let data = generate_random_data(size);
            b.iter(|| {
                let mut arr = data.clone();
                radix_sort_lsd(black_box(&mut arr));
            });
        });
        
        group.bench_with_input(BenchmarkId::new("radix_sort_msd", size), size, |b, &size| {
            let data = generate_random_data(size);
            b.iter(|| {
                let mut arr = data.clone();
                radix_sort_msd(black_box(&mut arr));
            });
        });
    }
    
    group.finish();
}

fn bench_sorted_data(c: &mut Criterion) {
    let mut group = c.benchmark_group("already_sorted");
    
    for size in [1000, 10000].iter() {
        group.bench_with_input(BenchmarkId::new("quick_sort", size), size, |b, &size| {
            let data = generate_sorted_data(size);
            b.iter(|| {
                let mut arr = data.clone();
                quick_sort(black_box(&mut arr));
            });
        });
        
        group.bench_with_input(BenchmarkId::new("insertion_sort", size), size, |b, &size| {
            let data = generate_sorted_data(size);
            b.iter(|| {
                let mut arr = data.clone();
                insertion_sort(black_box(&mut arr));
            });
        });
    }
    
    group.finish();
}

fn bench_reverse_data(c: &mut Criterion) {
    let mut group = c.benchmark_group("reverse_sorted");
    
    for size in [1000, 10000].iter() {
        group.bench_with_input(BenchmarkId::new("quick_sort", size), size, |b, &size| {
            let data = generate_reverse_data(size);
            b.iter(|| {
                let mut arr = data.clone();
                quick_sort(black_box(&mut arr));
            });
        });
        
        group.bench_with_input(BenchmarkId::new("heap_sort", size), size, |b, &size| {
            let data = generate_reverse_data(size);
            b.iter(|| {
                let mut arr = data.clone();
                heap_sort(black_box(&mut arr));
            });
        });
    }
    
    group.finish();
}

criterion_group!(
    benches,
    bench_comparison_sorts,
    bench_simple_sorts,
    bench_integer_sorts,
    bench_sorted_data,
    bench_reverse_data
);
criterion_main!(benches);
