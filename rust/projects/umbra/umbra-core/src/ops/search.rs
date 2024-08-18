use std::collections::HashMap;
use crate::types::*;

pub const SEMANTIC_WEIGHT: f64 = 0.5;
pub const BM25_WEIGHT: f64 = 0.3;
pub const ENTITY_WEIGHT: f64 = 0.2;

/// Multi-signal score fusion and ranking.
pub fn score_and_rank(
    semantic: Vec<ScoredMemory>,
    bm25_scores: &HashMap<String, f64>,
    entity_boosts: &HashMap<String, f64>,
    threshold: f64,
    top_k: usize,
) -> Vec<SearchResult> {
    let mut fused = Vec::new();
    for mem in semantic {
        let kw = bm25_scores.get(&mem.id).copied().unwrap_or(0.0);
        let ent = entity_boosts.get(&mem.id).copied().unwrap_or(0.0);
        let score = SEMANTIC_WEIGHT * mem.score + BM25_WEIGHT * kw + ENTITY_WEIGHT * ent;
        if score >= threshold {
            fused.push(SearchResult {
                id: mem.id,
                memory: mem.memory,
                score,
                created_at: mem.payload.get("created_at").cloned(),
                updated_at: mem.payload.get("updated_at").cloned(),
                user_id: mem.payload.get("user_id").cloned(),
                agent_id: mem.payload.get("agent_id").cloned(),
                run_id: mem.payload.get("run_id").cloned(),
                actor_id: mem.payload.get("actor_id").cloned(),
                role: mem.payload.get("role").cloned(),
                metadata: mem.payload,
            });
        }
    }
    fused.sort_by(|a, b| b.score.partial_cmp(&a.score).unwrap_or(std::cmp::Ordering::Equal));
    fused.truncate(top_k);
    fused
}
