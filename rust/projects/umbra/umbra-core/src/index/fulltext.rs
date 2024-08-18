use std::collections::HashMap;

use arrow_array::{Array, Float32Array, StringArray};
use lance::dataset::Dataset as LanceDataset;
use lance_index::scalar::FullTextSearchQuery;

use crate::types::MemoryFilters;
use crate::UmbraResult;

/// Perform BM25 full-text search and return memory_id -> normalized score.
pub async fn bm25_search(
    dataset: &LanceDataset,
    query_text: &str,
    top_k: usize,
    filters: Option<&MemoryFilters>,
) -> UmbraResult<HashMap<String, f64>> {
    let query = FullTextSearchQuery::new(query_text.to_string());
    let mut scanner = dataset.scan();
    scanner
        .full_text_search(query)
        .map_err(|e| crate::UmbraError::Internal(format!("fts: {e}")))?;
    scanner
        .limit(Some(top_k as i64), None)
        .map_err(|e| crate::UmbraError::Internal(format!("limit: {e}")))?;

    if let Some(f) = filters {
        let mut conditions = Vec::new();
        if let Some(ref uid) = f.user_id {
            conditions.push(format!("user_id = '{}'", uid));
        }
        if let Some(ref aid) = f.agent_id {
            conditions.push(format!("agent_id = '{}'", aid));
        }
        if let Some(ref rid) = f.run_id {
            conditions.push(format!("run_id = '{}'", rid));
        }
        if !conditions.is_empty() {
            scanner
                .filter(&conditions.join(" AND "))
                .map_err(|e| crate::UmbraError::Internal(format!("filter: {e}")))?;
        }
    }

    let stream = scanner
        .try_into_stream()
        .await
        .map_err(|e| crate::UmbraError::Internal(format!("fts scan: {e}")))?;

    use futures::TryStreamExt;
    let batches: Vec<_> = stream
        .try_collect()
        .await
        .map_err(|e| crate::UmbraError::Internal(format!("fts collect: {e}")))?;

    let mut scores = HashMap::new();
    for batch in batches {
        let id_arr = batch
            .column_by_name("id")
            .and_then(|c| c.as_any().downcast_ref::<StringArray>());
        let score_arr = batch
            .column_by_name("_score")
            .and_then(|c| c.as_any().downcast_ref::<Float32Array>());

        for row in 0..batch.num_rows() {
            if let (Some(id_a), Some(score_a)) = (id_arr, score_arr) {
                let id = id_a.value(row).to_string();
                let raw = score_a.value(row) as f64;
                // Simple sigmoid normalization for BM25
                let norm = if raw > 0.0 {
                    1.0 / (1.0 + (-2.0 * (raw - 1.0)).exp())
                } else {
                    0.0
                };
                scores.insert(id, norm);
            }
        }
    }
    Ok(scores)
}
