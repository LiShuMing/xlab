use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Document {
    pub id: String,
    pub type_: String, // "url" or "note"
    pub title: String,
    pub url: Option<String>,
    pub content: Option<String>,
    pub captured_at: String,
    pub clean_text_path: Option<String>,
    pub raw_html_path: Option<String>,
    pub status: String,
    pub topics: Vec<String>,
    pub entities: Vec<String>,
    pub word_count: i32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Analysis {
    pub id: String,
    pub document_id: String,
    pub mode: String,
    pub created_at: String,
    pub cost_ms: i64,
    pub result_json: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReviewItem {
    pub id: String,
    pub type_: String,
    pub item_id: String,
    pub item_type: String,
    pub front: String,
    pub back: String,
    pub context: Option<String>,
    pub due_at: String,
    pub interval: i64,
    pub ease: f64,
    pub last_score: Option<i32>,
    pub streak: i32,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Reflection {
    pub id: String,
    pub date: String,
    pub key_win: Option<String>,
    pub avoidance: Option<String>,
    pub next_fix: Option<String>,
    pub deep_work_min: i32,
    pub family_min: i32,
    pub sleep_h: f64,
    pub notes: Option<String>,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReflectionStats {
    pub total_reflections: i32,
    pub avg_deep_work_min: f64,
    pub avg_family_min: f64,
    pub avg_sleep_h: f64,
    pub current_streak: i32,
    pub recent_wins: Vec<String>,
    pub common_avoidance: Vec<String>,
}
