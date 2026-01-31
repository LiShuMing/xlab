//! Benchmarking framework for sorting algorithms
//!
//! This module provides tools to measure and compare the performance
//! of different sorting algorithms on various data distributions.

use super::SortAlgorithm;
use std::time::{Duration, Instant};

/// Maximum time allowed for a single benchmark run
const MAX_BENCHMARK_TIME: Duration = Duration::from_secs(30);

/// Minimum number of runs for statistical significance
const MIN_RUNS: usize = 3;

/// Maximum number of runs to prevent excessive time
const MAX_RUNS: usize = 100;

/// Target measurement time per benchmark
const TARGET_TIME: Duration = Duration::from_millis(100);

/// Result of a single benchmark run
#[derive(Debug, Clone)]
pub struct BenchmarkResult {
    /// Algorithm used
    pub algorithm: SortAlgorithm,
    /// Input size
    pub size: usize,
    /// Data distribution type
    pub distribution: DataDistribution,
    /// Number of runs performed
    pub runs: usize,
    /// Mean execution time
    pub mean_time: Duration,
    /// Minimum execution time
    pub min_time: Duration,
    /// Maximum execution time
    pub max_time: Duration,
    /// Standard deviation
    pub std_dev: Duration,
    /// Whether the sort produced correct results
    pub correct: bool,
}

impl BenchmarkResult {
    /// Format the result as a table row
    pub fn format_row(&self) -> String {
        format!(
            "| {:<15} | {:>10} | {:>12} | {:>10} | {:>10} | {:>8} | {:>6} |",
            self.algorithm.short_name(),
            self.size,
            format_duration(self.mean_time),
            format_duration(self.min_time),
            format_duration(self.max_time),
            format_duration(self.std_dev),
            if self.correct { "✓" } else { "✗" }
        )
    }

    /// Get throughput in elements per second
    pub fn throughput(&self) -> f64 {
        self.size as f64 / self.mean_time.as_secs_f64()
    }
}

/// Types of data distributions for testing
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum DataDistribution {
    /// Random values
    Random,
    /// Already sorted
    Sorted,
    /// Reverse sorted
    Reverse,
    /// Nearly sorted (few swaps needed)
    NearlySorted,
    /// Few unique values
    FewUnique,
    /// All same values
    AllEqual,
}

impl DataDistribution {
    /// All available distributions
    pub fn all() -> &'static [DataDistribution] {
        &[
            DataDistribution::Random,
            DataDistribution::Sorted,
            DataDistribution::Reverse,
            DataDistribution::NearlySorted,
            DataDistribution::FewUnique,
            DataDistribution::AllEqual,
        ]
    }

    /// Get human-readable name
    pub fn name(&self) -> &'static str {
        match self {
            DataDistribution::Random => "Random",
            DataDistribution::Sorted => "Sorted",
            DataDistribution::Reverse => "Reverse",
            DataDistribution::NearlySorted => "Nearly Sorted",
            DataDistribution::FewUnique => "Few Unique",
            DataDistribution::AllEqual => "All Equal",
        }
    }

    /// Generate test data of the given size
    pub fn generate(&self, size: usize) -> Vec<i32> {
        use fastrand::Rng;
        let mut rng = Rng::new();

        match self {
            DataDistribution::Random => {
                (0..size).map(|_| rng.i32(0..1_000_000)).collect()
            }
            DataDistribution::Sorted => (0..size as i32).collect(),
            DataDistribution::Reverse => (0..size as i32).rev().collect(),
            DataDistribution::NearlySorted => {
                let mut arr: Vec<i32> = (0..size as i32).collect();
                // Swap ~1% of elements
                for _ in 0..size / 100 {
                    let i = rng.usize(0..size);
                    let j = rng.usize(0..size);
                    arr.swap(i, j);
                }
                arr
            }
            DataDistribution::FewUnique => {
                (0..size).map(|_| rng.i32(0..10)).collect()
            }
            DataDistribution::AllEqual => vec![42; size],
        }
    }
}

/// Run a single benchmark
pub fn run_benchmark(
    algorithm: SortAlgorithm,
    distribution: DataDistribution,
    size: usize,
) -> BenchmarkResult {
    let mut times = Vec::new();
    let mut correct = true;
    let start_time = Instant::now();

    // Run at least MIN_RUNS times
    for _ in 0..MIN_RUNS {
        let time = run_single(algorithm, distribution, size);
        times.push(time);

        // Check correctness on first run
        if times.len() == 1 {
            correct = verify_sort(algorithm, distribution, size);
        }

        // Stop if we've exceeded target time
        if start_time.elapsed() > TARGET_TIME {
            break;
        }
    }

    // Continue running until we have stable measurements or hit limits
    while times.len() < MAX_RUNS && start_time.elapsed() < MAX_BENCHMARK_TIME {
        let time = run_single(algorithm, distribution, size);
        times.push(time);

        // Check if we have enough samples
        if times.len() >= MIN_RUNS {
            let mean = mean_duration(&times);
            let std_dev = std_dev_duration(&times, mean);
            // Stop if relative standard deviation is low enough
            if (std_dev.as_nanos() as f64) / (mean.as_nanos() as f64) < 0.05 {
                break;
            }
        }
    }

    let mean_time = mean_duration(&times);
    let std_dev = std_dev_duration(&times, mean_time);

    BenchmarkResult {
        algorithm,
        size,
        distribution,
        runs: times.len(),
        mean_time,
        min_time: *times.iter().min().unwrap_or(&Duration::ZERO),
        max_time: *times.iter().max().unwrap_or(&Duration::ZERO),
        std_dev,
        correct,
    }
}

/// Run a single iteration of the benchmark
fn run_single(algorithm: SortAlgorithm, distribution: DataDistribution, size: usize) -> Duration {
    let mut data = distribution.generate(size);

    // Skip algorithms that are too slow for large inputs
    if should_skip(algorithm, size) {
        return Duration::from_secs(999);
    }

    let start = Instant::now();
    run_sort(algorithm, &mut data);
    start.elapsed()
}

/// Determine if an algorithm should be skipped for large inputs
fn should_skip(algorithm: SortAlgorithm, size: usize) -> bool {
    // O(n²) algorithms become very slow for large inputs
    let o_n_squared_limit = 100_000;

    match algorithm {
        SortAlgorithm::Bubble
        | SortAlgorithm::Selection
        | SortAlgorithm::Insertion
        | SortAlgorithm::Gnome => size > o_n_squared_limit,
        _ => false,
    }
}

/// Run the specified sort algorithm on the data
fn run_sort(algorithm: SortAlgorithm, data: &mut [i32]) {
    use SortAlgorithm::*;
    use super::*;

    match algorithm {
        Bubble => bubble_sort(data),
        Selection => selection_sort(data),
        Insertion => insertion_sort(data),
        Shell => shell_sort(data),
        Gnome => gnome_sort(data),
        Comb => comb_sort(data),
        Quick => quick_sort(data),
        Merge => merge_sort(data),
        Heap => heap_sort(data),
        Tim => tim_sort(data),
        Intro => intro_sort(data),
        Counting => {
            if let Some(&max) = data.iter().max() {
                if max >= 0 {
                    counting_sort(data, max);
                }
            }
        }
        RadixLsd => radix_sort_lsd(data),
        RadixMsd => radix_sort_msd(data),
        Bucket => bucket_sort(data),
        Flash => flash_sort(data),
    }
}

/// Verify that the sort produces correct results
fn verify_sort(algorithm: SortAlgorithm, distribution: DataDistribution, size: usize) -> bool {
    let mut data = distribution.generate(size);

    if should_skip(algorithm, size) {
        return true; // Skip verification for skipped algorithms
    }

    run_sort(algorithm, &mut data);

    // Check if sorted
    data.windows(2).all(|w| w[0] <= w[1])
}

/// Calculate mean duration
fn mean_duration(times: &[Duration]) -> Duration {
    if times.is_empty() {
        return Duration::ZERO;
    }
    let sum: Duration = times.iter().sum();
    sum / times.len() as u32
}

/// Calculate standard deviation of durations
fn std_dev_duration(times: &[Duration], mean: Duration) -> Duration {
    if times.len() < 2 {
        return Duration::ZERO;
    }

    let variance: f64 = times
        .iter()
        .map(|&t| {
            let diff = t.as_nanos() as f64 - mean.as_nanos() as f64;
            diff * diff
        })
        .sum::<f64>()
        / (times.len() - 1) as f64;

    Duration::from_nanos(variance.sqrt() as u64)
}

/// Format a duration for display
fn format_duration(d: Duration) -> String {
    if d.as_secs() > 0 {
        format!("{:.2}s", d.as_secs_f64())
    } else if d.as_millis() > 0 {
        format!("{}ms", d.as_millis())
    } else if d.as_micros() > 0 {
        format!("{}µs", d.as_micros())
    } else {
        format!("{}ns", d.as_nanos())
    }
}

/// Compare multiple algorithms on multiple distributions
pub fn compare_algorithms(
    algorithms: &[SortAlgorithm],
    distributions: &[DataDistribution],
    sizes: &[usize],
) -> Vec<BenchmarkResult> {
    let mut results = Vec::new();

    for &algorithm in algorithms {
        for &distribution in distributions {
            for &size in sizes {
                println!(
                    "Benchmarking {} on {} data (n={})...",
                    algorithm.name(),
                    distribution.name(),
                    size
                );
                let result = run_benchmark(algorithm, distribution, size);
                results.push(result);
            }
        }
    }

    results
}

/// Print results as a formatted table
pub fn print_results_table(results: &[BenchmarkResult]) {
    // Header
    println!(
        "\n| {:<15} | {:>10} | {:>12} | {:>10} | {:>10} | {:>8} | {:>6} |",
        "Algorithm", "Size", "Mean", "Min", "Max", "StdDev", "OK"
    );
    println!(
        "|{}|{}|{}|{}|{}|{}|{}|",
        "-".repeat(17),
        "-".repeat(12),
        "-".repeat(14),
        "-".repeat(12),
        "-".repeat(12),
        "-".repeat(10),
        "-".repeat(8)
    );

    // Results grouped by distribution
    let mut current_dist = None;
    for result in results {
        if current_dist != Some(result.distribution) {
            current_dist = Some(result.distribution);
            println!("\n### {} ###", result.distribution.name());
        }
        println!("{}", result.format_row());
    }
}

/// Generate a performance ranking
pub fn rank_algorithms(results: &[BenchmarkResult]) -> Vec<(SortAlgorithm, f64)> {
    use std::collections::HashMap;

    let mut scores: HashMap<SortAlgorithm, Vec<f64>> = HashMap::new();

    // Group by (size, distribution) and assign scores
    let mut grouped: std::collections::HashMap<(usize, DataDistribution), Vec<&BenchmarkResult>> =
        std::collections::HashMap::new();

    for result in results {
        grouped
            .entry((result.size, result.distribution))
            .or_default()
            .push(result);
    }

    for (_, group) in grouped {
        let mut sorted = group.clone();
        sorted.sort_by_key(|r| r.mean_time);

        // Assign scores (1.0 = best, decreases for worse)
        for (i, result) in sorted.iter().enumerate() {
            let score = 1.0 / (1 + i) as f64;
            scores.entry(result.algorithm).or_default().push(score);
        }
    }

    // Average scores
    let mut ranking: Vec<(SortAlgorithm, f64)> = scores
        .into_iter()
        .map(|(alg, s)| {
            let avg = s.iter().sum::<f64>() / s.len() as f64;
            (alg, avg)
        })
        .collect();

    ranking.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap());
    ranking
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_data_distribution_generate() {
        for dist in DataDistribution::all() {
            let data = dist.generate(100);
            assert_eq!(data.len(), 100);
        }
    }

    #[test]
    fn test_benchmark_quick_sort() {
        let result = run_benchmark(SortAlgorithm::Quick, DataDistribution::Random, 1000);
        assert!(result.correct);
        assert!(result.runs >= MIN_RUNS);
    }

    #[test]
    fn test_verify_sort() {
        assert!(verify_sort(SortAlgorithm::Quick, DataDistribution::Random, 100));
        assert!(verify_sort(SortAlgorithm::Merge, DataDistribution::Random, 100));
    }

    #[test]
    fn test_should_skip() {
        assert!(should_skip(SortAlgorithm::Bubble, 200_000));
        assert!(!should_skip(SortAlgorithm::Quick, 200_000));
    }

    #[test]
    fn test_format_duration() {
        assert!(format_duration(Duration::from_secs(2)).contains("s"));
        assert!(format_duration(Duration::from_millis(500)).contains("ms"));
        assert!(format_duration(Duration::from_micros(100)).contains("µs"));
    }
}
