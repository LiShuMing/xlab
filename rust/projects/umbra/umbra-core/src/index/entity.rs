use std::collections::HashMap;

use arrow_array::{Array, Float32Array, ListArray, StringArray};
use lance::dataset::Dataset as LanceDataset;

use crate::embedding::Embedder;
use crate::entity::Entity;
use crate::types::MemoryFilters;
use crate::UmbraResult;

const ENTITY_SIMILARITY_THRESHOLD: f64 = 0.5;

/// Compute entity-based retrieval boost for each memory.
/// Returns memory_id -> boost score in [0, entity_boost_weight].
pub async fn compute_entity_boosts(
    entity_dataset: &LanceDataset,
    query_entities: &[Entity],
    embedder: &dyn Embedder,
    filters: &MemoryFilters,
    entity_boost_weight: f64,
) -> UmbraResult<HashMap<String, f64>> {
    if query_entities.is_empty() {
        return Ok(HashMap::new());
    }

    // Deduplicate entities (max 8)
    let mut seen = std::collections::HashSet::new();
    let deduped: Vec<&Entity> = query_entities
        .iter()
        .take(8)
        .filter(|(typ, text)| {
            let key = format!("{}:{}", typ, text.to_lowercase());
            seen.insert(key)
        })
        .collect();

    let mut memory_boosts: HashMap<String, f64> = HashMap::new();

    for (_etype, entity_text) in &deduped {
        let vec = match embedder.embed(entity_text).await {
            Ok(v) => v,
            Err(_) => continue,
        };

        let query_array = Float32Array::from(vec);
        let mut scanner = entity_dataset.scan();
        if scanner
            .nearest("embedding", &query_array, 500)
            .is_err()
        {
            continue;
        }

        let mut conditions = Vec::new();
        if let Some(ref uid) = filters.user_id {
            conditions.push(format!("user_id = '{}'", uid));
        }
        if let Some(ref aid) = filters.agent_id {
            conditions.push(format!("agent_id = '{}'", aid));
        }
        if let Some(ref rid) = filters.run_id {
            conditions.push(format!("run_id = '{}'", rid));
        }
        if !conditions.is_empty() {
            let _ = scanner.filter(&conditions.join(" AND "));
        }

        let stream = match scanner.try_into_stream().await {
            Ok(s) => s,
            Err(_) => continue,
        };

        use futures::TryStreamExt;
        let batches: Vec<_> = match stream.try_collect().await {
            Ok(b) => b,
            Err(_) => continue,
        };

        for batch in batches {
            let score_arr = batch
                .column(batch.num_columns() - 1)
                .as_any()
                .downcast_ref::<Float32Array>()
                .cloned();

            let linked_arr = batch
                .column_by_name("linked_memory_ids")
                .and_then(|c| c.as_any().downcast_ref::<ListArray>())
                .cloned();

            for row in 0..batch.num_rows() {
                let similarity: f64 = score_arr
                    .as_ref()
                    .map(|a| (1.0 - a.value(row)) as f64)
                    .unwrap_or(0.0);

                if similarity < ENTITY_SIMILARITY_THRESHOLD {
                    continue;
                }

                if let Some(ref linked) = linked_arr {
                    let list = linked.value(row);
                    if let Some(str_list) =
                        list.as_any().downcast_ref::<StringArray>()
                    {
                        let n_linked = str_list.len().max(1) as f64;
                        let attenuation =
                            1.0 / (1.0 + 0.001 * (n_linked - 1.0).powi(2));
                        let boost = similarity * entity_boost_weight * attenuation;

                        for i in 0..str_list.len() {
                            let mem_id = str_list.value(i).to_string();
                            memory_boosts
                                .entry(mem_id)
                                .and_modify(|v| *v = v.max(boost))
                                .or_insert(boost);
                        }
                    }
                }
            }
        }
    }

    Ok(memory_boosts)
}
