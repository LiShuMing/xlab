use serde::Serialize;
use std::path::PathBuf;

#[derive(Debug, Clone)]
pub struct AppConfig {
    pub llm: LlmConfig,
    pub psql: PsqlConfig,
}

#[derive(Debug, Clone)]
pub struct LlmConfig {
    pub base_url: String,
    pub api_key: Option<String>,
    pub model: String,
    pub timeout_secs: u64,
}

#[derive(Debug, Clone)]
pub struct PsqlConfig {
    pub host: Option<String>,
    pub port: u16,
    pub user: Option<String>,
    pub password: Option<String>,
    pub default_db: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct RuntimeConfigStatus {
    pub llm_configured: bool,
    pub llm_base_url: String,
    pub llm_model: String,
    pub llm_timeout_secs: u64,
    pub psql_configured: bool,
    pub psql_host: Option<String>,
    pub psql_port: u16,
    pub psql_default_db: Option<String>,
}

impl AppConfig {
    pub fn load() -> Self {
        load_env_defaults();

        Self {
            llm: LlmConfig {
                base_url: env_or("LLM_BASE_URL", "https://api.anthropic.com/v1"),
                api_key: non_empty_env("LLM_API_KEY")
                    .or_else(|| non_empty_env("ANTHROPIC_API_KEY")),
                model: env_or("LLM_MODEL", "claude-sonnet-4-20250514"),
                timeout_secs: std::env::var("LLM_TIMEOUT")
                    .ok()
                    .and_then(|value| value.parse::<u64>().ok())
                    .unwrap_or(120),
            },
            psql: PsqlConfig {
                host: non_empty_env("PSQL_URL"),
                port: std::env::var("PSQL_PORT")
                    .ok()
                    .and_then(|value| value.parse::<u16>().ok())
                    .unwrap_or(5432),
                user: non_empty_env("PSQL_USER"),
                password: non_empty_env("PSQL_PASSWORD"),
                default_db: non_empty_env("PSQL_DEFAULT_DB"),
            },
        }
    }

    pub fn status(&self) -> RuntimeConfigStatus {
        RuntimeConfigStatus {
            llm_configured: self.llm.api_key.is_some(),
            llm_base_url: self.llm.base_url.clone(),
            llm_model: self.llm.model.clone(),
            llm_timeout_secs: self.llm.timeout_secs,
            psql_configured: self.psql.host.is_some()
                && self.psql.user.is_some()
                && self.psql.password.is_some()
                && self.psql.default_db.is_some(),
            psql_host: self.psql.host.clone(),
            psql_port: self.psql.port,
            psql_default_db: self.psql.default_db.clone(),
        }
    }
}

fn load_env_defaults() {
    let mut candidates = Vec::new();

    if let Ok(cwd) = std::env::current_dir() {
        candidates.push(cwd.join(".env"));
        if let Some(parent) = cwd.parent() {
            candidates.push(parent.join(".env"));
        }
    }

    if let Some(home) = dirs::home_dir() {
        candidates.push(home.join(".env"));
    }

    for path in candidates {
        merge_env_file(path);
    }
}

fn merge_env_file(path: PathBuf) {
    if !path.exists() {
        return;
    }

    if let Ok(iter) = dotenvy::from_path_iter(path) {
        for item in iter.flatten() {
            let (key, value) = item;
            if std::env::var_os(&key).is_none() {
                std::env::set_var(key, value);
            }
        }
    }
}

fn non_empty_env(key: &str) -> Option<String> {
    std::env::var(key)
        .ok()
        .map(|value| value.trim().to_string())
        .filter(|value| !value.is_empty())
}

fn env_or(key: &str, default: &str) -> String {
    non_empty_env(key).unwrap_or_else(|| default.to_string())
}
