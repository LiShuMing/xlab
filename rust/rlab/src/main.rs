//! rlab - Rust Learning and Algorithms Benchmark
//!
//! This binary provides two main modes:
//! 1. **Examples mode** (`--examples`): Run basic Rust learning examples
//! 2. **Addr2line mode** (`<elf-file> <address>`): Resolve addresses to source locations
//!
//! # Usage
//!
//! ```bash
//! # Run learning examples
//! cargo run -- --examples
//!
//! # Resolve address in binary
//! cargo run -- ./my_program 0x401234
//! ```

use std::env;
use std::process;

mod addr2line;
mod common;
mod examples;

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
        2 if args[1] == "--examples" => {
            // Run examples mode
            examples::run_examples();
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
    println!("Usage:");
    println!("  {} --examples          Run basic Rust learning examples", program_name);
    println!("  {} <elf-file> <addr>   Resolve address to source location", program_name);
    println!();
    println!("Examples:");
    println!("  {} --examples", program_name);
    println!("  {} ./target/debug/rlab 0x1234", program_name);
    println!("  {} /bin/ls 0x401000", program_name);
}

/// Run addr2line functionality
fn run_addr2line(elf_path: &str, addr_str: &str) -> Result<(), Box<dyn std::error::Error>> {
    // Parse address
    let addr = parse_address(addr_str)?;
    
    if addr < MIN_VALID_ADDR {
        eprintln!("Warning: Address 0x{:x} seems very low (possible null pointer)", addr);
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
    
    u64::from_str_radix(trimmed, 16)
        .map_err(|e| format!("Invalid hex address '{}': {}", s, e))
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
}
