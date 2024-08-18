use std::sync::Arc;
use tokio::sync::Mutex;

mod services;
mod models;
mod commands;

pub use models::{Document, ReviewItem, Reflection, ReflectionStats};
pub use services::database::Database;

#[derive(Clone)]
pub struct AppState {
    pub db_path: String,
    pub api_key: Arc<Mutex<Option<String>>>,
}

impl AppState {
    pub fn new() -> Self {
        Self {
            db_path: Self::get_db_path(),
            api_key: Arc::new(Mutex::new(None)),
        }
    }

    fn get_db_path() -> String {
        if let Some(path) = dirs::data_dir() {
            let ft_path = path.join("FragmentTutor");
            std::fs::create_dir_all(&ft_path).ok();
            ft_path.join("fragment_tutor.db").to_string_lossy().to_string()
        } else {
            "fragment_tutor.db".to_string()
        }
    }
}

#[cfg(mobile)]
mod mobile;

#[cfg(mobile)]
tauri::builder::mobile_entry_point!(run_mobile);

pub fn run() {
    tauri::Builder::default()
        .manage(AppState::new())
        .invoke_handler(tauri::generate_handler![
            // Utility
            commands::greet,
            commands::get_app_version,
            commands::get_data_dir,
            commands::initialize_app,
            // Documents
            commands::capture_url,
            commands::create_note,
            commands::get_documents,
            commands::get_document,
            commands::delete_document,
            commands::search_documents,
            commands::update_document_status,
            // Reviews
            commands::get_review_queue,
            commands::get_reviews_for_date,
            commands::submit_review,
            commands::create_vocab_card,
            commands::create_insight_card,
            // Reflections
            commands::save_reflection,
            commands::get_reflection,
            commands::get_reflection_log,
            commands::get_reflection_stats,
            // Analysis
            commands::quick_digest,
            commands::get_analysis,
            commands::analyze_document,
            // Settings
            commands::get_settings,
            commands::get_api_key_status,
            commands::save_api_key,
        ])
        .run(tauri::generate_context!())
        .expect("error while running FragmentTutor");
}
