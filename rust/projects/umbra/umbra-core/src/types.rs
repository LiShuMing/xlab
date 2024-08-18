use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// A chat message.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Message {
    pub role: String,
    pub content: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub name: Option<String>,
}

/// Session scoping filters. At least one of user_id, agent_id, run_id must be set.
#[derive(Debug, Clone, Default)]
pub struct MemoryFilters {
    pub user_id: Option<String>,
    pub agent_id: Option<String>,
    pub run_id: Option<String>,
}

impl MemoryFilters {
    /// Build deterministic session scope string for message windowing.
    pub fn to_session_scope(&self) -> String {
        let mut parts = Vec::new();
        if let Some(ref v) = self.user_id { parts.push(format!("user_id={}", v)); }
        if let Some(ref v) = self.agent_id { parts.push(format!("agent_id={}", v)); }
        if let Some(ref v) = self.run_id { parts.push(format!("run_id={}", v)); }
        parts.join("&")
    }

    /// Validate at least one entity ID is present.
    pub fn validate(&self) -> Result<(), crate::UmbraError> {
        if self.user_id.is_none() && self.agent_id.is_none() && self.run_id.is_none() {
            return Err(crate::UmbraError::Validation(
                "At least one of user_id, agent_id, run_id must be provided".into(),
            ));
        }
        Ok(())
    }

    pub fn to_payload_pairs(&self) -> Vec<(String, String)> {
        let mut pairs = Vec::new();
        if let Some(ref v) = self.user_id {
            pairs.push(("user_id".into(), v.clone()));
        }
        if let Some(ref v) = self.agent_id {
            pairs.push(("agent_id".into(), v.clone()));
        }
        if let Some(ref v) = self.run_id {
            pairs.push(("run_id".into(), v.clone()));
        }
        pairs
    }
}

/// Result of an add operation.
#[derive(Debug, Clone, Serialize)]
pub struct AddResult {
    pub id: String,
    pub memory: String,
    pub event: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub actor_id: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub role: Option<String>,
}

/// Result of a search operation.
#[derive(Debug, Clone, Serialize)]
pub struct SearchResult {
    pub id: String,
    pub memory: String,
    pub score: f64,
    pub created_at: Option<String>,
    pub updated_at: Option<String>,
    pub user_id: Option<String>,
    pub agent_id: Option<String>,
    pub run_id: Option<String>,
    pub actor_id: Option<String>,
    pub role: Option<String>,
    pub metadata: HashMap<String, String>,
}

/// Internal scored memory during retrieval.
#[derive(Debug, Clone)]
pub struct ScoredMemory {
    pub id: String,
    pub memory: String,
    pub score: f64,
    pub payload: HashMap<String, String>,
}

/// A history record for a memory change.
#[derive(Debug, Clone, Serialize)]
pub struct HistoryRecord {
    pub id: String,
    pub memory_id: String,
    pub old_memory: Option<String>,
    pub new_memory: Option<String>,
    pub event: String,
    pub actor_id: Option<String>,
    pub created_at: Option<String>,
    pub is_deleted: bool,
}
