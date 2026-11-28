use std::net::SocketAddr;
use std::sync::Arc;

use anyhow::Result;
use axum::body::Bytes;
use axum::extract::{Path, State};
use axum::http::StatusCode;
use axum::response::IntoResponse;
use axum::routing::get;
use axum::{Json, Router};
use serde_json::json;
use slatedb::Db;

use crate::store::CountingObjectStore;

#[derive(Clone)]
pub struct KvServerState {
    pub db: Arc<Db>,
    pub counted: Arc<CountingObjectStore>,
}

/// Build the thin HTTP KV router backed by a single SlateDB writer + Foyer cache.
///
/// Designed as the P2 migration pattern for Python/TypeScript/Go services
/// (`lyra`, `puppis`, etc.) so multiple clients share one warm cache and group
/// commit batch without contending on OSS writer fencing.
pub fn build_router(state: KvServerState) -> Router {
    Router::new()
        .route("/health", get(health))
        .route("/v1/stats", get(stats))
        .route("/v1/kv/{key}", get(get_kv).put(put_kv).delete(delete_kv))
        .with_state(state)
}

async fn health() -> impl IntoResponse {
    (StatusCode::OK, Json(json!({ "status": "ok" })))
}

async fn stats(State(state): State<KvServerState>) -> impl IntoResponse {
    (StatusCode::OK, Json(state.counted.snapshot()))
}

async fn get_kv(
    State(state): State<KvServerState>,
    Path(key): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    match state.db.get(key.as_bytes()).await {
        Ok(Some(val)) => Ok((StatusCode::OK, val)),
        Ok(None) => Err((StatusCode::NOT_FOUND, format!("key not found: {key}"))),
        Err(err) => Err((StatusCode::INTERNAL_SERVER_ERROR, err.to_string())),
    }
}

async fn put_kv(
    State(state): State<KvServerState>,
    Path(key): Path<String>,
    body: Bytes,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    let handle = state
        .db
        .put(key.as_bytes(), &body)
        .await
        .map_err(|err| (StatusCode::INTERNAL_SERVER_ERROR, err.to_string()))?;
    handle
        .await_durable()
        .await
        .map_err(|err| (StatusCode::INTERNAL_SERVER_ERROR, err.to_string()))?;
    Ok((StatusCode::OK, Json(json!({ "ok": true, "key": key }))))
}

async fn delete_kv(
    State(state): State<KvServerState>,
    Path(key): Path<String>,
) -> Result<impl IntoResponse, (StatusCode, String)> {
    let handle = state
        .db
        .delete(key.as_bytes())
        .await
        .map_err(|err| (StatusCode::INTERNAL_SERVER_ERROR, err.to_string()))?;
    handle
        .await_durable()
        .await
        .map_err(|err| (StatusCode::INTERNAL_SERVER_ERROR, err.to_string()))?;
    Ok((StatusCode::OK, Json(json!({ "ok": true, "key": key }))))
}

/// Bind and serve the HTTP KV service until Ctrl-C, then cleanly close SlateDB.
pub async fn serve_until_ctrl_c(bind: SocketAddr, state: KvServerState) -> Result<()> {
    let db = Arc::clone(&state.db);
    let listener = tokio::net::TcpListener::bind(bind).await?;
    println!(
        "SlateDB KV HTTP server listening on http://{}",
        listener.local_addr()?
    );
    axum::serve(listener, build_router(state))
        .with_graceful_shutdown(async {
            let _ = tokio::signal::ctrl_c().await;
        })
        .await?;
    db.close().await?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::store::build_memory_store;
    use tokio::io::{AsyncReadExt, AsyncWriteExt};
    use tokio::net::TcpStream;

    async fn raw_http(addr: SocketAddr, req: &str) -> Result<String> {
        let mut stream = TcpStream::connect(addr).await?;
        stream.write_all(req.as_bytes()).await?;
        let mut buf = Vec::new();
        stream.read_to_end(&mut buf).await?;
        Ok(String::from_utf8(buf)?)
    }

    #[tokio::test]
    async fn kv_http_server_handles_crud_and_stats() -> Result<()> {
        let counted = CountingObjectStore::new(build_memory_store());
        let db = Arc::new(Db::open("srv-test", counted.clone()).await?);
        let state = KvServerState {
            db: Arc::clone(&db),
            counted,
        };

        let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await?;
        let addr = listener.local_addr()?;
        let server = tokio::spawn(async move {
            let _ = axum::serve(listener, build_router(state)).await;
        });

        let put_resp = raw_http(
            addr,
            "PUT /v1/kv/hello HTTP/1.1\r\nHost: localhost\r\nContent-Length: 5\r\nConnection: close\r\n\r\nworld",
        )
        .await?;
        assert!(put_resp.starts_with("HTTP/1.1 200"));

        let get_resp = raw_http(
            addr,
            "GET /v1/kv/hello HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n",
        )
        .await?;
        assert!(get_resp.starts_with("HTTP/1.1 200"));
        assert!(get_resp.ends_with("world"));

        let del_resp = raw_http(
            addr,
            "DELETE /v1/kv/hello HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n",
        )
        .await?;
        assert!(del_resp.starts_with("HTTP/1.1 200"));

        let missing_resp = raw_http(
            addr,
            "GET /v1/kv/hello HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n",
        )
        .await?;
        assert!(missing_resp.starts_with("HTTP/1.1 404"));

        let stats_resp = raw_http(
            addr,
            "GET /v1/stats HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n",
        )
        .await?;
        assert!(stats_resp.starts_with("HTTP/1.1 200"));
        assert!(stats_resp.contains("put_ops"));

        server.abort();
        db.close().await?;
        Ok(())
    }
}
