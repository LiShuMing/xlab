use crate::AppState;
use crate::models::{Document, ReviewItem, Reflection, ReflectionStats};
use crate::services::database::Database;
use chrono::Utc;
use uuid::Uuid;

// Document Commands
#[tauri::command]
pub async fn capture_url(
    url: String,
    title: Option<String>,
    state: tauri::State<'_, AppState>,
) -> Result<Document, String> {
    let db = Database::connect(&state.db_path).await?;
    
    let html = crate::services::scraper::fetch_html(&url).await?;
    let extracted_title = crate::services::scraper::extract_title(&html);
    let clean_text = crate::services::scraper::extract_text(&html);
    let word_count = clean_text.split_whitespace().count() as i32;
    
    let final_title = title.unwrap_or(extracted_title);
    let now = Utc::now().to_rfc3339();
    let doc_id = Uuid::new_v4().to_string();
    
    let doc = Document {
        id: doc_id.clone(),
        type_: "url".to_string(),
        title: final_title,
        url: Some(url),
        content: Some(clean_text.clone()),
        captured_at: now.clone(),
        clean_text_path: None,
        raw_html_path: None,
        status: "captured".to_string(),
        topics: vec![],
        entities: vec![],
        word_count,
    };
    
    db.create_document(&doc).await?;
    Ok(doc)
}

#[tauri::command]
pub async fn create_note(
    title: String,
    content: String,
    state: tauri::State<'_, AppState>,
) -> Result<Document, String> {
    let db = Database::connect(&state.db_path).await?;
    
    let word_count = content.split_whitespace().count() as i32;
    let now = Utc::now().to_rfc3339();
    let doc_id = Uuid::new_v4().to_string();
    
    let doc = Document {
        id: doc_id,
        type_: "note".to_string(),
        title,
        url: None,
        content: Some(content),
        captured_at: now,
        clean_text_path: None,
        raw_html_path: None,
        status: "captured".to_string(),
        topics: vec![],
        entities: vec![],
        word_count,
    };
    
    db.create_document(&doc).await?;
    Ok(doc)
}

#[tauri::command]
pub async fn get_documents(
    limit: Option<i64>,
    offset: Option<i64>,
    state: tauri::State<'_, AppState>,
) -> Result<Vec<Document>, String> {
    let db = Database::connect(&state.db_path).await?;
    db.get_documents(limit.unwrap_or(50), offset.unwrap_or(0)).await
}

#[tauri::command]
pub async fn get_document(
    id: String,
    state: tauri::State<'_, AppState>,
) -> Result<Option<Document>, String> {
    let db = Database::connect(&state.db_path).await?;
    db.get_document(&id).await
}

#[tauri::command]
pub async fn delete_document(
    id: String,
    state: tauri::State<'_, AppState>,
) -> Result<bool, String> {
    let db = Database::connect(&state.db_path).await?;
    db.delete_document(&id).await
}

#[tauri::command]
pub async fn search_documents(
    query: String,
    state: tauri::State<'_, AppState>,
) -> Result<Vec<Document>, String> {
    let db = Database::connect(&state.db_path).await?;
    db.search_documents(&query).await
}

#[tauri::command]
pub async fn update_document_status(
    id: String,
    status: String,
    state: tauri::State<'_, AppState>,
) -> Result<bool, String> {
    let db = Database::connect(&state.db_path).await?;
    db.update_document_status(&id, &status).await
}

// Review Commands
#[tauri::command]
pub async fn get_reviews_for_date(
    date: String,
    state: tauri::State<'_, AppState>,
) -> Result<Vec<ReviewItem>, String> {
    let db = Database::connect(&state.db_path).await?;
    // For now, return empty vec - this would filter by date in a real implementation
    let all = db.get_review_queue().await?;
    Ok(all)
}

#[tauri::command]
pub async fn get_review_queue(
    state: tauri::State<'_, AppState>,
) -> Result<Vec<ReviewItem>, String> {
    let db = Database::connect(&state.db_path).await?;
    db.get_review_queue().await
}

#[tauri::command]
pub async fn submit_review(
    item_id: String,
    score: i32,
    state: tauri::State<'_, AppState>,
) -> Result<(), String> {
    let db = Database::connect(&state.db_path).await?;
    db.submit_review(&item_id, score).await
}

#[tauri::command]
pub async fn create_vocab_card(
    word: String,
    definition: String,
    context: String,
    _document_id: Option<String>,
    state: tauri::State<'_, AppState>,
) -> Result<ReviewItem, String> {
    let db = Database::connect(&state.db_path).await?;
    
    let now = Utc::now().to_rfc3339();
    let item_id = Uuid::new_v4().to_string();
    
    let item = ReviewItem {
        id: item_id.clone(),
        type_: "vocab".to_string(),
        item_id: item_id.clone(),
        item_type: "vocab".to_string(),
        front: word,
        back: definition,
        context: Some(context),
        due_at: now.clone(),
        interval: 0,
        ease: 2.5,
        last_score: None,
        streak: 0,
        created_at: now,
    };
    
    db.create_review_item(&item).await?;
    Ok(item)
}

#[tauri::command]
pub async fn create_insight_card(
    insight: String,
    context: String,
    _document_id: Option<String>,
    state: tauri::State<'_, AppState>,
) -> Result<ReviewItem, String> {
    let db = Database::connect(&state.db_path).await?;
    
    let now = Utc::now().to_rfc3339();
    let item_id = Uuid::new_v4().to_string();
    
    let item = ReviewItem {
        id: item_id.clone(),
        type_: "insight".to_string(),
        item_id: item_id.clone(),
        item_type: "insight".to_string(),
        front: insight.clone(),
        back: context.clone(),
        context: Some(context),
        due_at: now.clone(),
        interval: 0,
        ease: 2.5,
        last_score: None,
        streak: 0,
        created_at: now,
    };
    
    db.create_review_item(&item).await?;
    Ok(item)
}

// Reflection Commands
#[tauri::command]
pub async fn save_reflection(
    key_win: String,
    avoidance: String,
    next_fix: String,
    deep_work_min: i32,
    family_min: i32,
    sleep_h: f64,
    notes: Option<String>,
    state: tauri::State<'_, AppState>,
) -> Result<Reflection, String> {
    let db = Database::connect(&state.db_path).await?;
    
    let today = Utc::now().format("%Y-%m-%d").to_string();
    let now = Utc::now().to_rfc3339();
    
    let reflection = Reflection {
        id: Uuid::new_v4().to_string(),
        date: today,
        key_win: Some(key_win),
        avoidance: Some(avoidance),
        next_fix: Some(next_fix),
        deep_work_min,
        family_min,
        sleep_h,
        notes,
        created_at: now,
    };
    
    db.save_reflection(&reflection).await?;
    Ok(reflection)
}

#[tauri::command]
pub async fn get_reflection(
    date: String,
    state: tauri::State<'_, AppState>,
) -> Result<Option<Reflection>, String> {
    let db = Database::connect(&state.db_path).await?;
    db.get_reflection(&date).await
}

#[tauri::command]
pub async fn get_reflection_log(
    start_date: Option<String>,
    end_date: Option<String>,
    state: tauri::State<'_, AppState>,
) -> Result<Vec<Reflection>, String> {
    let db = Database::connect(&state.db_path).await?;
    db.get_reflection_log(start_date.as_deref(), end_date.as_deref()).await
}

#[tauri::command]
pub async fn get_reflection_stats(
    state: tauri::State<'_, AppState>,
) -> Result<ReflectionStats, String> {
    let db = Database::connect(&state.db_path).await?;
    db.get_reflection_stats().await
}

// Analysis Commands
#[tauri::command]
pub async fn get_analysis(
    document_id: String,
    state: tauri::State<'_, AppState>,
) -> Result<Option<crate::services::anthropic::QuickDigestResult>, String> {
    // For now, return None - in a real implementation this would fetch from the analyses table
    Ok(None)
}

#[tauri::command]
pub async fn analyze_document(
    document_id: String,
    mode: String,
    api_key: String,
    state: tauri::State<'_, AppState>,
) -> Result<String, String> {
    // Call quick_digest and return the result as JSON string
    let result = quick_digest(document_id, Some(api_key), state).await?;
    serde_json::to_string(&result).map_err(|e| e.to_string())
}

#[tauri::command]
pub async fn quick_digest(
    document_id: String,
    api_key: Option<String>,
    state: tauri::State<'_, AppState>,
) -> Result<crate::services::anthropic::QuickDigestResult, String> {
    let db = Database::connect(&state.db_path).await?;
    
    let doc = db.get_document(&document_id).await?;
    if doc.is_none() {
        return Err("Document not found".to_string());
    }
    let doc = doc.unwrap();
    
    let content = doc.content.unwrap_or_default();
    if content.is_empty() {
        return Err("Document has no content to analyze".to_string());
    }
    
    let key = if let Some(key) = api_key {
        key
    } else {
        let state_key = state.api_key.lock().await;
        state_key.clone().ok_or("No API key configured")?
    };
    
    crate::services::anthropic::quick_digest(&key, &content).await
}

// Settings Commands
#[tauri::command]
pub async fn get_settings(state: tauri::State<'_, AppState>) -> Result<serde_json::Value, String> {
    let key = state.api_key.lock().await;
    Ok(serde_json::json!({
        "anthropicApiKey": key.clone(),
        "notification": {
            "reviewReminder": true,
            "reviewTime": "09:00",
            "eveningReminder": true,
            "eveningTime": "18:00",
            "reflectionReminder": true,
            "reflectionInterval": 4
        },
        "dailyGoalReviews": 10,
        "dailyGoalDeepWorkMin": 120,
        "shortcutKey": "Cmd+Shift+N"
    }))
}

#[tauri::command]
pub async fn get_api_key_status(state: tauri::State<'_, AppState>) -> Result<bool, String> {
    let key = state.api_key.lock().await;
    Ok(key.is_some())
}

#[tauri::command]
pub async fn save_api_key(
    api_key: String,
    state: tauri::State<'_, AppState>,
) -> Result<(), String> {
    let mut state_key = state.api_key.lock().await;
    *state_key = Some(api_key);
    Ok(())
}

// Utility Commands
#[tauri::command]
pub fn greet(name: &str) -> String {
    format!("Hello, {}! Welcome to FragmentTutor.", name)
}

#[tauri::command]
pub fn get_app_version() -> String {
    env!("CARGO_PKG_VERSION").to_string()
}

#[tauri::command]
pub fn get_data_dir() -> String {
    if let Some(path) = dirs::data_dir() {
        path.join("FragmentTutor").to_string_lossy().to_string()
    } else {
        String::new()
    }
}

#[tauri::command]
pub async fn initialize_app(state: tauri::State<'_, AppState>) -> Result<(), String> {
    crate::services::database::run_migrations(&state.db_path).await
}
