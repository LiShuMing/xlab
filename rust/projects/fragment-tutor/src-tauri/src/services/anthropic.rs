use serde::{Deserialize, Serialize};
use std::time::Duration;

use super::config::LlmConfig;

#[derive(Serialize)]
struct ChatCompletionRequest {
    model: String,
    messages: Vec<ChatMessage>,
    temperature: f32,
    max_tokens: u32,
    response_format: ResponseFormat,
}

#[derive(Serialize)]
struct ChatMessage {
    role: String,
    content: String,
}

#[derive(Serialize)]
struct ResponseFormat {
    #[serde(rename = "type")]
    type_: String,
}

#[derive(Deserialize)]
struct ChatCompletionResponse {
    choices: Vec<Choice>,
}

#[derive(Deserialize)]
struct Choice {
    message: ResponseMessage,
}

#[derive(Deserialize)]
struct ResponseMessage {
    content: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct QuickDigestResult {
    pub thesis: String,
    #[serde(alias = "first_principles")]
    pub first_principles: Vec<String>,
    pub counterpoint: String,
    #[serde(alias = "micro_actions")]
    pub micro_actions: Vec<String>,
    pub vocab: Vec<VocabItem>,
    #[serde(alias = "key_insights")]
    pub key_insights: Vec<String>,
    #[serde(alias = "related_topics")]
    pub related_topics: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct VocabItem {
    pub word: String,
    pub definition: String,
    pub context: String,
    pub pronunciation: Option<String>,
}

pub async fn quick_digest(config: &LlmConfig, content: &str) -> Result<QuickDigestResult, String> {
    let api_key = config
        .api_key
        .as_deref()
        .ok_or_else(|| "LLM_API_KEY is not configured".to_string())?;

    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(config.timeout_secs))
        .build()
        .map_err(|e| e.to_string())?;

    let request = ChatCompletionRequest {
        model: config.model.clone(),
        temperature: 0.2,
        max_tokens: 1800,
        response_format: ResponseFormat {
            type_: "json_object".to_string(),
        },
        messages: vec![
            ChatMessage {
                role: "system".to_string(),
                content: system_prompt(),
            },
            ChatMessage {
                role: "user".to_string(),
                content: format!(
                    "请分析以下学习材料。只返回 JSON，不要输出 Markdown。\n\n{}",
                    truncate_content(content, 24_000)
                ),
            },
        ],
    };

    let response = client
        .post(chat_completions_url(&config.base_url))
        .bearer_auth(api_key)
        .json(&request)
        .send()
        .await
        .map_err(|e| format!("LLM request failed: {}", e))?;

    let status = response.status();
    let body = response.text().await.map_err(|e| e.to_string())?;
    if !status.is_success() {
        return Err(format!("LLM request failed with HTTP {}: {}", status, body));
    }

    let completion: ChatCompletionResponse =
        serde_json::from_str(&body).map_err(|e| format!("Invalid LLM response: {}", e))?;
    let content = completion
        .choices
        .first()
        .map(|choice| choice.message.content.as_str())
        .ok_or_else(|| "LLM response contains no choices".to_string())?;

    parse_digest(content)
}

fn system_prompt() -> String {
    [
        "你是 FragmentTutor 的学习材料分析器。",
        "目标：把碎片阅读材料转化为可复习、可行动的学习资产。",
        "必须返回一个 JSON object，字段固定为：",
        "thesis: string",
        "firstPrinciples: string[]，3-5 条",
        "counterpoint: string",
        "microActions: string[]，2-5 条",
        "vocab: { word, definition, context, pronunciation }[]，3-8 条",
        "keyInsights: string[]，3-5 条",
        "relatedTopics: string[]，3-8 条",
        "内容可以中文为主；术语可保留英文。",
    ]
    .join("\n")
}

fn chat_completions_url(base_url: &str) -> String {
    format!("{}/chat/completions", base_url.trim_end_matches('/'))
}

fn truncate_content(content: &str, max_chars: usize) -> String {
    let mut result = String::new();
    for ch in content.chars().take(max_chars) {
        result.push(ch);
    }
    result
}

fn parse_digest(content: &str) -> Result<QuickDigestResult, String> {
    let cleaned = content
        .trim()
        .trim_start_matches("```json")
        .trim_start_matches("```")
        .trim_end_matches("```")
        .trim();

    serde_json::from_str(cleaned).map_err(|e| format!("Invalid digest JSON: {}", e))
}
