//! Bloom Filter Performance Comparison Tool
//!
//! Compares three implementations:
//! - Classic Bloom Filter
//! - Split Block Bloom Filter (SBBF)
//! - XOR Filter

use std::time::{Duration, Instant};

mod classic;
mod split_block;
mod xor_filter;

use classic::BloomFilter;
use split_block::SplitBlockBloomFilter;
use xor_filter::XorFilter;

fn main() {
    println!("╔══════════════════════════════════════════════════════════════╗");
    println!("║     Bloom Filter Performance & False Positive Test Suite    ║");
    println!("╚══════════════════════════════════════════════════════════════╝\n");

    // Test configurations
    let test_sizes = vec![10_000, 100_000, 1_000_000];
    let target_fp_rate = 0.01; // 1%

    for &size in &test_sizes {
        println!("\n{}", "=".repeat(60));
        println!("Testing with {} items, target FP rate: {:.1}%", size, target_fp_rate * 100.0);
        println!("{}\n", ":".repeat(60));

        test_false_positive_rate(size, target_fp_rate);
        test_performance(size, target_fp_rate);
        test_memory_usage(size, target_fp_rate);
    }

    println!("\n{}", "=".repeat(60));
    println!("Summary & Recommendations");
    println!("{}\n", ":".repeat(60));
    print_summary();
}

/// Test false positive rates for all implementations
fn test_false_positive_rate(num_items: usize, target_fp_rate: f64) {
    println!("📊 FALSE POSITIVE RATE TESTS\n");

    // Generate test data
    let items: Vec<u64> = (0..num_items as u64).collect();
    let non_items: Vec<u64> = (num_items as u64..(2 * num_items) as u64).collect();

    // Classic Bloom Filter
    {
        let mut bf = BloomFilter::new(num_items, target_fp_rate);
        for item in &items {
            bf.insert(item);
        }

        let mut fp_count = 0;
        for item in &non_items {
            if bf.contains(item) {
                fp_count += 1;
            }
        }
        let actual_fp_rate = fp_count as f64 / non_items.len() as f64;
        let estimated_fp_rate = bf.current_fp_rate();

        println!("Classic Bloom Filter:");
        println!("  Target FP rate:    {:.4}%", target_fp_rate * 100.0);
        println!("  Actual FP rate:    {:.4}%", actual_fp_rate * 100.0);
        println!("  Estimated FP rate: {:.4}%", estimated_fp_rate * 100.0);
        println!();
    }

    // Split Block Bloom Filter
    {
        let mut bf = SplitBlockBloomFilter::new(num_items, target_fp_rate);
        for item in &items {
            bf.insert(item);
        }

        let mut fp_count = 0;
        for item in &non_items {
            if bf.contains(item) {
                fp_count += 1;
            }
        }
        let actual_fp_rate = fp_count as f64 / non_items.len() as f64;

        println!("Split Block Bloom Filter:");
        println!("  Target FP rate: {:.4}%", target_fp_rate * 100.0);
        println!("  Actual FP rate: {:.4}%", actual_fp_rate * 100.0);
        println!();
    }

    // XOR Filter
    {
        let bf = XorFilter::from_items(items.into_iter()).expect("XOR filter construction failed");

        let mut fp_count = 0;
        for item in &non_items {
            if bf.contains(item) {
                fp_count += 1;
            }
        }
        let actual_fp_rate = fp_count as f64 / non_items.len() as f64;
        let theoretical_fp = bf.theoretical_fp_rate();

        println!("XOR Filter:");
        println!("  Theoretical FP: {:.4}%", theoretical_fp * 100.0);
        println!("  Actual FP rate: {:.4}%", actual_fp_rate * 100.0);
        println!();
    }
}

/// Test insertion and lookup performance
fn test_performance(num_items: usize, target_fp_rate: f64) {
    println!("⚡ PERFORMANCE TESTS\n");

    let items: Vec<u64> = (0..num_items as u64).collect();
    let test_items: Vec<u64> = ((2 * num_items) as u64..(3 * num_items) as u64).collect();

    // Classic Bloom Filter
    {
        let mut bf = BloomFilter::new(num_items, target_fp_rate);

        // Insertion benchmark
        let start = Instant::now();
        for item in &items {
            bf.insert(item);
        }
        let insert_time = start.elapsed();

        // Lookup benchmark
        let start = Instant::now();
        for item in &test_items {
            let _ = bf.contains(item);
        }
        let lookup_time = start.elapsed();

        print_perf_stats("Classic Bloom Filter", insert_time, lookup_time, num_items);
    }

    // Split Block Bloom Filter
    {
        let mut bf = SplitBlockBloomFilter::new(num_items, target_fp_rate);

        let start = Instant::now();
        for item in &items {
            bf.insert(item);
        }
        let insert_time = start.elapsed();

        let start = Instant::now();
        for item in &test_items {
            let _ = bf.contains(item);
        }
        let lookup_time = start.elapsed();

        print_perf_stats("Split Block Bloom Filter", insert_time, lookup_time, num_items);
    }

    // XOR Filter (construction is bulk)
    {
        let start = Instant::now();
        let bf = XorFilter::from_items(items.clone().into_iter())
            .expect("XOR filter construction failed");
        let construct_time = start.elapsed();

        let start = Instant::now();
        for item in &test_items {
            let _ = bf.contains(item);
        }
        let lookup_time = start.elapsed();

        println!("XOR Filter:");
        println!("  Construction:  {:?} ({:.2} ns/op)",
            construct_time,
            construct_time.as_nanos() as f64 / num_items as f64
        );
        println!("  Lookup:        {:?} ({:.2} ns/op)",
            lookup_time,
            lookup_time.as_nanos() as f64 / num_items as f64
        );
        println!();
    }
}

fn print_perf_stats(name: &str, insert_time: Duration, lookup_time: Duration, num_items: usize) {
    println!("{}:", name);
    println!("  Insert:  {:?} ({:.2} ns/op)",
        insert_time,
        insert_time.as_nanos() as f64 / num_items as f64
    );
    println!("  Lookup:  {:?} ({:.2} ns/op)",
        lookup_time,
        lookup_time.as_nanos() as f64 / num_items as f64
    );
    println!();
}

/// Test memory usage
fn test_memory_usage(num_items: usize, target_fp_rate: f64) {
    println!("💾 MEMORY USAGE\n");

    let items: Vec<u64> = (0..num_items as u64).collect();

    // Classic Bloom Filter
    {
        let bf = BloomFilter::new(num_items, target_fp_rate);
        let bytes = bf.memory_usage();
        let bits_per_item = (bytes * 8) as f64 / num_items as f64;
        println!("Classic Bloom Filter:     {:>8} bytes ({:.2} bits/item)", bytes, bits_per_item);
    }

    // Split Block Bloom Filter
    {
        let bf = SplitBlockBloomFilter::new(num_items, target_fp_rate);
        let bytes = bf.memory_usage();
        let bits_per_item = (bytes * 8) as f64 / num_items as f64;
        println!("Split Block Bloom Filter: {:>8} bytes ({:.2} bits/item)", bytes, bits_per_item);
    }

    // XOR Filter
    {
        let bf = XorFilter::from_items(items.into_iter()).unwrap();
        let bytes = bf.memory_usage();
        let bits_per_item = (bytes * 8) as f64 / num_items as f64;
        println!("XOR Filter:               {:>8} bytes ({:.2} bits/item)", bytes, bits_per_item);
    }

    println!();
}

/// Print summary and recommendations
fn print_summary() {
    println!("Comparison Summary:\n");

    println!("┌─────────────────────────┬────────────┬────────────┬────────────┐");
    println!("│ {:<23} │ {:<10} │ {:<10} │ {:<10} │", "Filter Type", "Memory", "Insert", "Lookup");
    println!("├─────────────────────────┼────────────┼────────────┼────────────┤");
    println!("│ {:<23} │ {:<10} │ {:<10} │ {:<10} │", "Classic Bloom", "High", "Fast", "Fast");
    println!("│ {:<23} │ {:<10} │ {:<10} │ {:<10} │", "Split Block", "High", "Fastest", "Fastest");
    println!("│ {:<23} │ {:<10} │ {:<10} │ {:<10} │", "XOR Filter", "Lowest", "N/A*", "Fast");
    println!("└─────────────────────────┴────────────┴────────────┴────────────┘");
    println!("* XOR Filter requires bulk construction\n");

    println!("Recommendations:");
    println!("  • Use Classic Bloom Filter for general-purpose use");
    println!("  • Use Split Block Bloom Filter for cache-sensitive workloads");
    println!("  • Use XOR Filter when memory is constrained and data is static");
    println!("  • XOR Filter has ~30% lower memory than Bloom at similar FP rates\n");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_all_filters_work() {
        let items: Vec<i32> = (0..1000).collect();

        // Test Classic
        let mut bf = BloomFilter::new(1000, 0.01);
        for item in &items {
            bf.insert(item);
        }
        assert!(items.iter().all(|i| bf.contains(i)));

        // Test Split Block
        let mut bf = SplitBlockBloomFilter::new(1000, 0.01);
        for item in &items {
            bf.insert(item);
        }
        assert!(items.iter().all(|i| bf.contains(i)));

        // Test XOR
        let bf = XorFilter::from_items(items.clone().into_iter()).unwrap();
        assert!(items.iter().all(|i| bf.contains(i)));
    }
}
