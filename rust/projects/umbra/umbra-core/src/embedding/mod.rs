pub mod openai;

use async_trait::async_trait;
use crate::UmbraResult;

/// A batch of embedding vectors. Each inner Vec has dimension D.
pub type EmbeddingBatch = Vec<Vec<f32>>;

#[async_trait]
pub trait Embedder: Send + Sync {
    /// Embed a single text into a vector.
    async fn embed(&self, text: &str) -> UmbraResult<Vec<f32>>;

    /// Embed multiple texts. Default implementation calls embed() in a loop.
    async fn embed_batch(&self, texts: &[&str]) -> UmbraResult<EmbeddingBatch> {
        let mut results = Vec::with_capacity(texts.len());
        for text in texts {
            results.push(self.embed(text).await?);
        }
        Ok(results)
    }

    /// Dimension of the embedding vectors.
    fn dimension(&self) -> usize;
}
