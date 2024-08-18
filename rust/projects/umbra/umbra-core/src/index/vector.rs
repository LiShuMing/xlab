use std::collections::HashMap;

use arrow_array::{Array, Float32Array, StringArray};
use lance::dataset::Dataset as LanceDataset;

use crate::types::{MemoryFilters, ScoredMemory};
use crate::UmbraResult;

/// Perform ANN vector search using Lance's native IVF-PQ index.
pub async fn ann_search(
    dataset: &LanceDataset,
    embedding_column: &str,
    query_vec: &[f32],
    top_k: usize,
    filters: Option<&MemoryFilters>,
) -> UmbraResult<Vec<ScoredMemory>> {
    let query_array = Float32Array::from(query_vec.to_vec());
    let mut scanner = dataset.scan();
    scanner
        .nearest(embedding_column, &query_array, top_k)
        .map_err(|e| crate::UmbraError::Internal(format!("nearest: {e}")))?;

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
        .map_err(|e| crate::UmbraError::Internal(format!("scan: {e}")))?;

    use futures::TryStreamExt;
    let batches: Vec<_> = stream
        .try_collect()
        .await
        .map_err(|e| crate::UmbraError::Internal(format!("collect: {e}")))?;

    let mut results = Vec::new();
    for batch in batches {
        let id_arr = batch
            .column_by_name("id")
            .and_then(|c| c.as_any().downcast_ref::<StringArray>());
        let mem_arr = batch
            .column_by_name("memory")
            .and_then(|c| c.as_any().downcast_ref::<StringArray>());
        // _distance is returned by Lance nearest() as the last column
        let score_arr = batch
            .column_by_name("_distance")
            .or_else(|| Some(batch.column(batch.num_columns() - 1)))
            .and_then(|c| c.as_any().downcast_ref::<Float32Array>());

        for row in 0..batch.num_rows() {
            let id = id_arr
                .map(|a| a.value(row).to_string())
                .unwrap_or_default();
            let memory = mem_arr
                .map(|a| a.value(row).to_string())
                .unwrap_or_default();
            let dist: f32 = score_arr.map(|a| a.value(row)).unwrap_or(1.0);
            // Convert cosine distance to similarity
            let score = (1.0 - dist) as f64;

            let mut payload = HashMap::new();
            for col in batch.schema().fields() {
                if let Some(arr) = batch.column_by_name(col.name()) {
                    if let Some(sa) = arr.as_any().downcast_ref::<StringArray>() {
                        if !sa.is_null(row) {
                            payload.insert(col.name().to_string(), sa.value(row).to_string());
                        }
                    }
                }
            }

            results.push(ScoredMemory {
                id,
                memory,
                score,
                payload,
            });
        }
    }

    Ok(results)
}
