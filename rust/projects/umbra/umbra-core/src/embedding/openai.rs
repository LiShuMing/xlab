use async_trait::async_trait;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use crate::{UmbraError, UmbraResult};
use super::Embedder;

#[derive(Clone)]
pub struct OpenAIEmbedder {
    client: Client,
    api_key: String,
    model: String,
    base_url: String,
    /// NOTE: This dimension is NOT validated against actual API responses.
    /// The caller must ensure it matches the model's output dimension
    /// (e.g., text-embedding-3-small → 1536).
    dimension: usize,
}

impl std::fmt::Debug for OpenAIEmbedder {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("OpenAIEmbedder")
            .field("model", &self.model)
            .field("base_url", &self.base_url)
            .field("dimension", &self.dimension)
            .field("api_key", &"<redacted>")
            .finish()
    }
}

#[derive(Serialize)]
struct EmbeddingRequest {
    model: String,
    input: EmbeddingInput,
    encoding_format: String,
}

#[derive(Serialize)]
#[serde(untagged)]
enum EmbeddingInput {
    Single(String),
    Batch(Vec<String>),
}

#[derive(Deserialize)]
struct EmbeddingResponse {
    data: Vec<EmbeddingData>,
}

#[derive(Deserialize)]
struct EmbeddingData {
    embedding: Vec<f32>,
}

impl OpenAIEmbedder {
    /// Create a new OpenAI embedder.
    ///
    /// Note: `dimension` is NOT validated against the actual API response.
    /// The caller must ensure it matches the model's output dimension
    /// (e.g., text-embedding-3-small → 1536).
    pub fn new(api_key: String, model: String, base_url: String, dimension: usize) -> Self {
        Self {
            client: Client::new(),
            api_key,
            model,
            base_url,
            dimension,
        }
    }

    async fn request_embeddings(&self, input: EmbeddingInput) -> UmbraResult<Vec<Vec<f32>>> {
        let req = EmbeddingRequest {
            model: self.model.clone(),
            input,
            encoding_format: "float".to_string(),
        };
        let url = format!("{}/embeddings", self.base_url.trim_end_matches('/'));
        let resp = self.client
            .post(&url)
            .header("Authorization", format!("Bearer {}", self.api_key))
            .json(&req)
            .send()
            .await
            .map_err(|e| UmbraError::Embedding(format!("request failed: {e}")))?;
        if !resp.status().is_success() {
            let status = resp.status();
            let body = resp.text().await.unwrap_or_default();
            return Err(UmbraError::Embedding(format!("HTTP {status}: {body}")));
        }
        let emb: EmbeddingResponse = resp
            .json()
            .await
            .map_err(|e| UmbraError::Embedding(format!("parse response: {e}")))?;
        Ok(emb.data.into_iter().map(|d| d.embedding).collect())
    }
}

#[async_trait]
impl Embedder for OpenAIEmbedder {
    async fn embed(&self, text: &str) -> UmbraResult<Vec<f32>> {
        let results = self.request_embeddings(EmbeddingInput::Single(text.to_string())).await?;
        results.into_iter().next()
            .ok_or_else(|| UmbraError::Embedding("empty response data".into()))
    }

    async fn embed_batch(&self, texts: &[&str]) -> UmbraResult<super::EmbeddingBatch> {
        if texts.is_empty() {
            return Ok(vec![]);
        }
        self.request_embeddings(EmbeddingInput::Batch(texts.iter().map(|s| s.to_string()).collect())).await
    }

    fn dimension(&self) -> usize {
        self.dimension
    }
}

/// Mock embedder for testing — returns deterministic vectors based on text hash.
pub struct MockEmbedder {
    dimension: usize,
}

impl MockEmbedder {
    pub fn new(dimension: usize) -> Self {
        Self { dimension }
    }
}

#[async_trait]
impl Embedder for MockEmbedder {
    async fn embed(&self, text: &str) -> UmbraResult<Vec<f32>> {
        use std::collections::hash_map::DefaultHasher;
        use std::hash::{Hash, Hasher};
        let mut hasher = DefaultHasher::new();
        text.hash(&mut hasher);
        let seed = hasher.finish();
        let mut vec = Vec::with_capacity(self.dimension);
        for i in 0..self.dimension {
            let val = ((seed.wrapping_mul(i as u64 + 1)) % 1000) as f32 / 1000.0;
            vec.push(val);
        }
        // L2 normalize
        let norm: f32 = vec.iter().map(|x| x * x).sum::<f32>().sqrt();
        if norm > 0.0 {
            vec.iter_mut().for_each(|x| *x /= norm);
        }
        Ok(vec)
    }

    fn dimension(&self) -> usize {
        self.dimension
    }
}
