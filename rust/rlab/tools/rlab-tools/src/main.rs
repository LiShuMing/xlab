//! rlab-tools - CLI tools for the rlab library
//!
//! This binary provides several modes:
//! 1. **Sort benchmark mode** (`--sort-bench`): Run sorting algorithm performance comparisons
//! 2. **Addr2line mode** (`<elf-file> <address>`): Resolve addresses to source locations
//!
//! # Usage
//!
//! ```bash
//! # Run sorting benchmarks
//! rlab --sort-bench
//! rlab --sort-bench --size 1000,10000 --algorithms quick,merge,heap
//!
//! # Resolve address in binary
//! rlab ./my_program 0x401234
//! ```

use std::env;
use std::process;

use rlab::sort::{
    benchmark::{compare_algorithms, print_results_table, rank_algorithms, DataDistribution},
    SortAlgorithm,
};

mod addr2line;

/// Minimum address for valid resolution (avoids resolving null pointers)
const MIN_VALID_ADDR: u64 = 0x1000;

/// Program entry point
fn main() {
    let args: Vec<String> = env::args().collect();

    match args.len() {
        1 => {
            // No arguments - show help
            print_help(&args[0]);
            process::exit(1);
        }
        2 => match args[1].as_str() {
            "--sort-bench" => {
                run_sort_benchmark(&args);
            }
            "--help" | "-h" => {
                print_help(&args[0]);
            }
            "--version" | "-v" => {
                println!("rlab-tools 0.1.0 - CLI tools for rlab");
            }
            _ => {
                eprintln!("Error: Unknown option '{}'", args[1]);
                print_help(&args[0]);
                process::exit(1);
            }
        },
        _ if args[1] == "--sort-bench" => {
            run_sort_benchmark(&args);
        }
        3 => {
            // Addr2line mode
            if let Err(e) = run_addr2line(&args[1], &args[2]) {
                eprintln!("Error: {}", e);
                process::exit(1);
            }
        }
        _ => {
            eprintln!("Error: Too many arguments\n");
            print_help(&args[0]);
            process::exit(1);
        }
    }
}

/// Print usage help
fn print_help(program_name: &str) {
    println!("rlab-tools - CLI tools for rlab\n");
    println!("Usage:");
    println!("  {} --sort-bench [options]   Run sorting algorithm benchmarks", program_name);
    println!("  {} <elf-file> <addr>        Resolve address to source location", program_name);
    println!("  {} --help, -h               Show this help", program_name);
    println!("  {} --version, -v            Show version", program_name);
    println!();
    println!("Sort Benchmark Options:");
    println!("  --algorithms <list>         Comma-separated list (default: all)");
    println!("                              Available: bubble,selection,insertion,shell,gnome,comb,");
    println!("                                         quick,merge,heap,tim,intro,");
    println!("                                         counting,radix-lsd,radix-msd,bucket,flash");
    println!("  --sizes <list>              Comma-separated sizes (default: 100,1000,10000)");
    println!("  --distributions <list>      Comma-separated (default: random,sorted,reverse)");
    println!("                              Available: random,sorted,reverse,nearly-sorted,few-unique,all-equal");
    println!();
    println!("Examples:");
    println!("  {} --sort-bench", program_name);
    println!("  {} --sort-bench --sizes 1000,5000 --algorithms quick,merge,heap", program_name);
    println!("  {} /usr/bin/ls 0x401000", program_name);
}

/// Parse and run sorting benchmarks
fn run_sort_benchmark(args: &[String]) {
    // Default values
    let mut sizes = vec![100, 1000, 10_000];
    let mut algorithms: Option<Vec<SortAlgorithm>> = None;
    let mut distributions: Option<Vec<DataDistribution>> = None;

    // Parse arguments
    let mut i = 2;
    while i < args.len() {
        match args[i].as_str() {
            "--sizes" => {
                if i + 1 < args.len() {
                    sizes = args[i + 1]
                        .split(',')
                        .filter_map(|s| s.parse().ok())
                        .collect();
                    i += 2;
                } else {
                    eprintln!("Error: --sizes requires a value");
                    process::exit(1);
                }
            }
            "--algorithms" => {
                if i + 1 < args.len() {
                    algorithms = Some(parse_algorithms(&args[i + 1]));
                    i += 2;
                } else {
                    eprintln!("Error: --algorithms requires a value");
                    process::exit(1);
                }
            }
            "--distributions" => {
                if i + 1 < args.len() {
                    distributions = Some(parse_distributions(&args[i + 1]));
                    i += 2;
                } else {
                    eprintln!("Error: --distributions requires a value");
                    process::exit(1);
                }
            }
            _ => {
                eprintln!("Error: Unknown option '{}'", args[i]);
                process::exit(1);
            }
        }
    }

    // Use defaults if not specified
    let algorithms = algorithms.unwrap_or_else(|| SortAlgorithm::general_purpose().to_vec());
    let distributions = distributions.unwrap_or_else(|| {
        vec![
            DataDistribution::Random,
            DataDistribution::Sorted,
            DataDistribution::Reverse,
        ]
    });

    // Validate
    if sizes.is_empty() {
        eprintln!("Error: No valid sizes specified");
        process::exit(1);
    }
    if algorithms.is_empty() {
        eprintln!("Error: No valid algorithms specified");
        process::exit(1);
    }

    // Print configuration
    println!("\n=== Sorting Algorithm Benchmark ===\n");
    println!(
        "Algorithms: {}",
        algorithms
            .iter()
            .map(|a| a.name())
            .collect::<Vec<_>>()
            .join(", ")
    );
    println!("Sizes: {:?}", sizes);
    println!(
        "Distributions: {}",
        distributions
            .iter()
            .map(|d| d.name())
            .collect::<Vec<_>>()
            .join(", ")
    );
    println!();

    // Run benchmarks
    let results = compare_algorithms(&algorithms, &distributions, &sizes);

    // Print results
    print_results_table(&results);

    // Print ranking
    println!("\n=== Performance Ranking ===");
    let ranking = rank_algorithms(&results);
    for (i, (alg, score)) in ranking.iter().enumerate() {
        println!("{}. {} (score: {:.2})", i + 1, alg.name(), score);
    }
}

/// Parse algorithm names
fn parse_algorithms(s: &str) -> Vec<SortAlgorithm> {
    s.split(',')
        .filter_map(|name| match name.trim() {
            "bubble" => Some(SortAlgorithm::Bubble),
            "selection" => Some(SortAlgorithm::Selection),
            "insertion" => Some(SortAlgorithm::Insertion),
            "shell" => Some(SortAlgorithm::Shell),
            "gnome" => Some(SortAlgorithm::Gnome),
            "comb" => Some(SortAlgorithm::Comb),
            "quick" => Some(SortAlgorithm::Quick),
            "merge" => Some(SortAlgorithm::Merge),
            "heap" => Some(SortAlgorithm::Heap),
            "tim" => Some(SortAlgorithm::Tim),
            "intro" => Some(SortAlgorithm::Intro),
            "counting" => Some(SortAlgorithm::Counting),
            "radix-lsd" => Some(SortAlgorithm::RadixLsd),
            "radix-msd" => Some(SortAlgorithm::RadixMsd),
            "bucket" => Some(SortAlgorithm::Bucket),
            "flash" => Some(SortAlgorithm::Flash),
            _ => {
                eprintln!("Warning: Unknown algorithm '{}'", name);
                None
            }
        })
        .collect()
}

/// Parse distribution names
fn parse_distributions(s: &str) -> Vec<DataDistribution> {
    s.split(',')
        .filter_map(|name| match name.trim() {
            "random" => Some(DataDistribution::Random),
            "sorted" => Some(DataDistribution::Sorted),
            "reverse" => Some(DataDistribution::Reverse),
            "nearly-sorted" => Some(DataDistribution::NearlySorted),
            "few-unique" => Some(DataDistribution::FewUnique),
            "all-equal" => Some(DataDistribution::AllEqual),
            _ => {
                eprintln!("Warning: Unknown distribution '{}'", name);
                None
            }
        })
        .collect()
}

/// Run addr2line functionality
fn run_addr2line(elf_path: &str, addr_str: &str) -> Result<(), Box<dyn std::error::Error>> {
    // Parse address
    let addr = parse_address(addr_str)?;

    if addr < MIN_VALID_ADDR {
        eprintln!(
            "Warning: Address 0x{:x} seems very low (possible null pointer)",
            addr
        );
    }

    // Create resolver
    let resolver = addr2line::Addr2Line::new(elf_path)
        .map_err(|e| format!("Failed to open '{}': {}", elf_path, e))?;

    // Try to resolve address
    match resolver.resolve(addr)? {
        Some(location) => {
            println!("{}", location);
        }
        None => {
            // Fallback: try to find nearest symbol
            match resolver.nearest_symbol(addr)? {
                Some(symbol) => {
                    println!("{} (+0x0) [no line info]", symbol);
                }
                None => {
                    println!("??:0:0 [address not found]");
                }
            }
        }
    }

    Ok(())
}

/// Parse an address string (hex with optional 0x prefix)
fn parse_address(s: &str) -> Result<u64, String> {
    let trimmed = s.trim_start_matches("0x").trim_start_matches("0X");

    if trimmed.is_empty() {
        return Err(format!("Empty address: '{}'", s));
    }

    u64::from_str_radix(trimmed, 16).map_err(|e| format!("Invalid hex address '{}': {}", s, e))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_address() {
        assert_eq!(parse_address("0x1234").unwrap(), 0x1234);
        assert_eq!(parse_address("1234").unwrap(), 0x1234);
        assert_eq!(parse_address("0XABC").unwrap(), 0xABC);
        assert_eq!(parse_address("0x0").unwrap(), 0);
        assert_eq!(parse_address("ffffffff").unwrap(), 0xffffffff);
    }

    #[test]
    fn test_parse_address_invalid() {
        assert!(parse_address("").is_err());
        assert!(parse_address("0x").is_err());
        assert!(parse_address("xyz").is_err());
        assert!(parse_address("0xxyz").is_err());
    }

    #[test]
    fn test_parse_algorithms() {
        let algs = parse_algorithms("quick,merge,heap");
        assert_eq!(algs.len(), 3);
        assert!(algs.contains(&SortAlgorithm::Quick));
        assert!(algs.contains(&SortAlgorithm::Merge));
        assert!(algs.contains(&SortAlgorithm::Heap));
    }

    #[test]
    fn test_parse_distributions() {
        let dists = parse_distributions("random,sorted,reverse");
        assert_eq!(dists.len(), 3);
        assert!(dists.contains(&DataDistribution::Random));
        assert!(dists.contains(&DataDistribution::Sorted));
        assert!(dists.contains(&DataDistribution::Reverse));
    }
}
