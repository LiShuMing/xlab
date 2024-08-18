use std::sync::Arc;

use datafusion::execution::context::SessionContext;
use umbra_core::embedding::openai::OpenAIEmbedder;
use umbra_core::embedding::Embedder;
use umbra_core::index::IndexConfig;
use umbra_core::ops::{MemoryOps, MemoryOpsImpl};
use umbra_core::storage::StorageConfig as CoreStorageConfig;
use umbra_server::config::AppConfig;
use umbra_server::service::UmbraMemoryService;
use umbra_server::umbra_proto::memory_service_server::MemoryServiceServer;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt::init();

    let config = AppConfig::load()?;
    tracing::info!(
        "Loaded config: grpc={}, flight={}",
        config.server.grpc_port,
        config.server.flight_sql_port
    );

    // Init embedder
    let embedder: Arc<dyn Embedder> = match config.embedding.provider.as_str() {
        "openai" => Arc::new(OpenAIEmbedder::new(
            config.embedding.api_key.clone(),
            config.embedding.model.clone(),
            config.embedding.base_url.clone(),
            config.embedding.dimensions,
        )),
        _ => {
            tracing::warn!(
                "Unknown embedding provider '{}', using mock embedder",
                config.embedding.provider
            );
            Arc::new(umbra_core::embedding::openai::MockEmbedder::new(
                config.embedding.dimensions,
            ))
        }
    };

    let index_config = IndexConfig::default();
    let storage_config = CoreStorageConfig {
        base_path: config.storage.base_path.clone(),
    };

    // Init DataFusion context
    let ctx = Arc::new(SessionContext::new());
    umbra_core::query::register_all(&ctx)?;

    // Build MemoryOps
    let ops: Arc<dyn MemoryOps> =
        Arc::new(MemoryOpsImpl::new(embedder, index_config, storage_config));

    // Start gRPC server
    let grpc_addr = format!("0.0.0.0:{}", config.server.grpc_port).parse()?;
    let service = UmbraMemoryService::new(ops);
    let grpc_handle = tokio::spawn(async move {
        tonic::transport::Server::builder()
            .add_service(MemoryServiceServer::new(service))
            .serve(grpc_addr)
            .await
            .expect("gRPC server failed");
    });

    // Start Flight SQL
    let flight_addr = format!("0.0.0.0:{}", config.server.flight_sql_port).parse()?;
    let flight_handle = tokio::spawn(async move {
        umbra_server::flight::serve_flight_sql(ctx, flight_addr)
            .await
            .expect("Flight SQL server failed");
    });

    tracing::info!(
        "Umbra server started — gRPC: {}, Flight SQL: {}",
        config.server.grpc_port,
        config.server.flight_sql_port
    );

    tokio::signal::ctrl_c().await?;
    grpc_handle.abort();
    flight_handle.abort();

    tracing::info!("Umbra server shut down");
    Ok(())
}
