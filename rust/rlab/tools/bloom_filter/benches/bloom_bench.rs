//! Criterion Benchmarks for Bloom Filter Implementations

use criterion::{black_box, criterion_group, criterion_main, BenchmarkId, Criterion, Throughput};

use bloom_filter::classic::BloomFilter;
use bloom_filter::split_block::SplitBlockBloomFilter;
use bloom_filter::xor_filter::XorFilter;

fn bench_insertion(c: &mut Criterion) {
    let mut group = c.benchmark_group("insertion");

    for size in [1000, 10000, 100000].iter() {
        group.throughput(Throughput::Elements(*size as u64));

        // Classic Bloom Filter
        group.bench_with_input(BenchmarkId::new("classic", size), size, |b, &size| {
            let items: Vec<u64> = (0..size as u64).collect();
            b.iter(|| {
                let mut bf = BloomFilter::new(size, 0.01);
                for item in &items {
                    bf.insert(black_box(item));
                }
            });
        });

        // Split Block Bloom Filter
        group.bench_with_input(BenchmarkId::new("split_block", size), size, |b, &size| {
            let items: Vec<u64> = (0..size as u64).collect();
            b.iter(|| {
                let mut bf = SplitBlockBloomFilter::new(size, 0.01);
                for item in &items {
                    bf.insert(black_box(item));
                }
            });
        });

        // XOR Filter (bulk construction)
        group.bench_with_input(BenchmarkId::new("xor_filter", size), size, |b, &size| {
            let items: Vec<u64> = (0..size as u64).collect();
            b.iter(|| {
                let _bf = XorFilter::from_items(items.clone().into_iter()).unwrap();
            });
        });
    }

    group.finish();
}

fn bench_lookup(c: &mut Criterion) {
    let mut group = c.benchmark_group("lookup");

    for size in [1000, 10000, 100000].iter() {
        group.throughput(Throughput::Elements(*size as u64));

        let items: Vec<u64> = (0..*size as u64).collect();
        let test_items: Vec<u64> = ((*size as u64)..(2 * *size) as u64).collect();

        // Classic Bloom Filter
        {
            let mut bf = BloomFilter::new(*size, 0.01);
            for item in &items {
                bf.insert(item);
            }

            group.bench_with_input(
                BenchmarkId::new("classic", size),
                &test_items,
                |b, test_items| {
                    b.iter(|| {
                        for item in test_items {
                            black_box(bf.contains(black_box(item)));
                        }
                    });
                },
            );
        }

        // Split Block Bloom Filter
        {
            let mut bf = SplitBlockBloomFilter::new(*size, 0.01);
            for item in &items {
                bf.insert(item);
            }

            group.bench_with_input(
                BenchmarkId::new("split_block", size),
                &test_items,
                |b, test_items| {
                    b.iter(|| {
                        for item in test_items {
                            black_box(bf.contains(black_box(item)));
                        }
                    });
                },
            );
        }

        // XOR Filter
        {
            let bf = XorFilter::from_items(items.clone().into_iter()).unwrap();

            group.bench_with_input(
                BenchmarkId::new("xor_filter", size),
                &test_items,
                |b, test_items| {
                    b.iter(|| {
                        for item in test_items {
                            black_box(bf.contains(black_box(item)));
                        }
                    });
                },
            );
        }
    }

    group.finish();
}

fn bench_lookup_single(c: &mut Criterion) {
    let mut group = c.benchmark_group("lookup_single");

    let size = 10000;
    let items: Vec<u64> = (0..size as u64).collect();

    // Classic Bloom Filter
    {
        let mut bf = BloomFilter::new(size, 0.01);
        for item in &items {
            bf.insert(item);
        }
        let test_item = 999999u64;

        group.bench_function("classic", |b| {
            b.iter(|| bf.contains(black_box(&test_item)))
        });
    }

    // Split Block Bloom Filter
    {
        let mut bf = SplitBlockBloomFilter::new(size, 0.01);
        for item in &items {
            bf.insert(item);
        }
        let test_item = 999999u64;

        group.bench_function("split_block", |b| {
            b.iter(|| bf.contains(black_box(&test_item)))
        });
    }

    // XOR Filter
    {
        let bf = XorFilter::from_items(items.into_iter()).unwrap();
        let test_item = 999999u64;

        group.bench_function("xor_filter", |b| {
            b.iter(|| bf.contains(black_box(&test_item)))
        });
    }

    group.finish();
}

criterion_group!(
    benches,
    bench_insertion,
    bench_lookup,
    bench_lookup_single
);
criterion_main!(benches);
