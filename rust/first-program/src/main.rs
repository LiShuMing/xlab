//! this is a crate library
use chrono::Utc;
use std::process;

fn main() {
    println!("Hello, world!");
    println!("Heloo, time now is {:?}", Utc::now());
    println!("{}", get_process_id());
}

/// function
/// ```
/// ```
fn get_process_id() -> u32 {
    return process::id();
}

#[test]
fn test_if_process_id_is_returned() {
    assert! (get_process_id() > 0);
}
