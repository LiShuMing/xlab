use std::env;
use std::io;

use grace_hash_join::{hybrid_grace_hash_join, JoinConfig, Row};

fn main() -> io::Result<()> {
    let config = parse_config()?;
    let (build, probe) = demo_data();
    let result = hybrid_grace_hash_join(&build, &probe, &config)?;

    println!("Hybrid Grace Hash Join trace");
    for (step, event) in result.events.iter().enumerate() {
        println!("  {:>2}. {event}", step + 1);
    }

    println!("\nJoined rows");
    let mut rows = result.rows;
    rows.sort();
    for row in &rows {
        println!(
            "  key={:<2} build={:<12} probe={}",
            row.key, row.build_payload, row.probe_payload
        );
    }

    println!("\nStats\n{:#?}", result.stats);
    Ok(())
}

fn parse_config() -> io::Result<JoinConfig> {
    let mut config = JoinConfig::default();
    let mut args = env::args().skip(1);
    while let Some(arg) = args.next() {
        let value = match arg.as_str() {
            "--memory-rows" | "--partitions" | "--max-depth" => args.next().ok_or_else(|| {
                io::Error::new(
                    io::ErrorKind::InvalidInput,
                    format!("missing value for {arg}"),
                )
            })?,
            "--help" | "-h" => {
                print_help();
                std::process::exit(0);
            }
            _ => {
                return Err(io::Error::new(
                    io::ErrorKind::InvalidInput,
                    format!("unknown argument: {arg}"),
                ));
            }
        };
        let number = value.parse::<usize>().map_err(|error| {
            io::Error::new(
                io::ErrorKind::InvalidInput,
                format!("invalid value for {arg}: {error}"),
            )
        })?;
        match arg.as_str() {
            "--memory-rows" => config.memory_budget_rows = number,
            "--partitions" => config.partitions = number,
            "--max-depth" => config.max_repartition_depth = number,
            _ => unreachable!(),
        }
    }
    Ok(config)
}

fn print_help() {
    println!(
        "Usage: grace-hash-join [OPTIONS]\n\n\
         Options:\n\
           --memory-rows N  Build rows allowed in one local hash table (default: 4)\n\
           --partitions N   Power-of-two partitions per level (default: 4)\n\
           --max-depth N    Recursive repartition limit (default: 3)"
    );
}

fn demo_data() -> (Vec<Row>, Vec<Row>) {
    let build = vec![
        Row::new(1, "customer-1"),
        Row::new(2, "customer-2a"),
        Row::new(2, "customer-2b"),
        Row::new(3, "customer-3"),
        Row::new(4, "customer-4"),
        Row::new(5, "customer-5"),
        Row::new(6, "customer-6"),
        Row::new(7, "customer-7"),
        Row::new(8, "customer-8"),
        Row::null("build-null"),
    ];
    let probe = vec![
        Row::new(1, "order-101"),
        Row::new(2, "order-102"),
        Row::new(2, "order-103"),
        Row::new(5, "order-104"),
        Row::new(8, "order-105"),
        Row::new(6, "order-106"),
        Row::new(99, "order-miss"),
        Row::null("probe-null"),
    ];
    (build, probe)
}
