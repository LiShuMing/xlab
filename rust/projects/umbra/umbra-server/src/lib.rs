//! Umbra AI memory database — gRPC + Flight SQL server.

pub mod config;
pub mod flight;
pub mod service;

// Include generated proto code
pub mod umbra_proto {
    tonic::include_proto!("umbra");
}
