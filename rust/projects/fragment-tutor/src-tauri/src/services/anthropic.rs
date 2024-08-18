use serde::{Deserialize, Serialize};

const API_URL: &str = "https://api.anthropic.com/v1/messages";

#[derive(Serialize)]
struct Message {
    role: String,
    content: String,
}

#[derive(Serialize)]
struct MessageRequest {
    model: String,
    max_tokens: u32,
    messages: Vec<Message>,
    system: String,
}

#[derive(Deserialize)]
struct MessageResponse {
    id: String,
    content: Vec<ContentBlock>,
    model: String,
    usage: Usage,
}

#[derive(Deserialize)]
struct ContentBlock {
    type_: String,
    text: Option<String>,
}

#[derive(Deserialize)]
struct Usage {
    input_tokens: u32,
    output_tokens: u32,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct QuickDigestResult {
    pub thesis: String,
    pub first_principles: Vec<String>,
    pub counterpoint: String,
    pub micro_actions: Vec<String>,
    pub vocab: Vec<VocabItem>,
    pub key_insights: Vec<String>,
    pub related_topics: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VocabItem {
    pub word: String,
    pub definition: String,
    pub context: String,
    pub pronunciation: Option<String>,
}

pub async fn quick_digest(_api_key: &str, _content: &str) -> Result<QuickDigestResult, String> {
    Ok(QuickDigestResult {
        thesis: "Sample thesis - This is a placeholder for the actual analysis.".to_string(),
        first_principles: vec![
            "First principle extracted from content".to_string(),
            "Second fundamental concept".to_string(),
            "Third key concept".to_string(),
        ],
        counterpoint: "A potential counter-argument or limitation of this perspective.".to_string(),
        micro_actions: vec![
            "Take action 1 today".to_string(),
            "Implement action 2 this week".to_string(),
        ],
        vocab: vec![
            VocabItem {
                word: "example".to_string(),
                definition: "A thing characteristic of its kind or illustrating a general rule".to_string(),
                context: "Used in the context of...".to_string(),
                pronunciation: Some("ig-ZAM-puhl".to_string()),
            }
        ],
        key_insights: vec![
            "Key insight 1 from the content".to_string(),
        ],
        related_topics: vec![
            "Related topic 1".to_string(),
        ],
    })
}

pub async fn extract_vocab(_api_key: &str, _content: &str, _num_terms: u32) 
    -> Result<Vec<VocabItem>, String> {
    Ok(vec![
        VocabItem {
            word: "example".to_string(),
            definition: "A representative form or pattern".to_string(),
            context: "Sample context".to_string(),
            pronunciation: Some("ig-ZAM-puhl".to_string()),
        }
    ])
}
