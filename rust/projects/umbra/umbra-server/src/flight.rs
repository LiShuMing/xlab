use std::sync::Arc;

/// Placeholder: Flight SQL server will be wired when datafusion-flight-sql-server
/// is added as a dependency. The crate exists (v0.4.16) but needs version
/// compatibility verification with DataFusion 43.
///
/// See: <https://crates.io/crates/datafusion-flight-sql-server>
pub async fn serve_flight_sql(
    _ctx: Arc<datafusion::execution::context::SessionContext>,
    addr: std::net::SocketAddr,
) -> anyhow::Result<()> {
    tracing::warn!(
        "Flight SQL server not yet wired — would listen on {addr}. \
         Add datafusion-flight-sql-server dependency to enable."
    );
    // Keep the task alive so main can shut it down gracefully.
    tokio::signal::ctrl_c().await?;
    Ok(())
}
