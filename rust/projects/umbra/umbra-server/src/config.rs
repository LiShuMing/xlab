use figment::{
    providers::{Env, Toml},
    Figment,
};
use figment::providers::Format;
use serde::Deserialize;

#[derive(Debug, Clone, Deserialize)]
pub struct ServerConfig {
    pub grpc_port: u16,
    pub flight_sql_port: u16,
    #[serde(default = "default_graceful_timeout")]
    pub graceful_timeout_secs: u64,
}

fn default_graceful_timeout() -> u64 {
    30
}

#[derive(Debug, Clone, Deserialize)]
pub struct StorageConfig {
    pub base_path: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct EmbeddingConfig {
    pub provider: String,
    pub model: String,
    pub dimensions: usize,
    pub api_key: String,
    #[serde(default = "default_base_url")]
    pub base_url: String,
    #[serde(default = "default_batch_size")]
    pub batch_size: usize,
}

fn default_base_url() -> String {
    "https://api.openai.com/v1".to_string()
}
fn default_batch_size() -> usize {
    100
}

#[derive(Debug, Clone, Deserialize)]
pub struct AppConfig {
    pub server: ServerConfig,
    pub storage: StorageConfig,
    pub embedding: EmbeddingConfig,
    #[serde(default)]
    pub search: SearchConfig,
}

#[derive(Debug, Clone, Deserialize)]
pub struct SearchConfig {
    #[serde(default = "default_semantic_weight")]
    pub semantic_weight: f64,
    #[serde(default = "default_bm25_weight")]
    pub bm25_weight: f64,
    #[serde(default = "default_entity_weight")]
    pub entity_boost_weight: f64,
    #[serde(default = "default_top_k")]
    pub default_top_k: usize,
    #[serde(default = "default_threshold")]
    pub default_threshold: f64,
}

fn default_semantic_weight() -> f64 {
    0.5
}
fn default_bm25_weight() -> f64 {
    0.3
}
fn default_entity_weight() -> f64 {
    0.2
}
fn default_top_k() -> usize {
    20
}
fn default_threshold() -> f64 {
    0.1
}

impl Default for SearchConfig {
    fn default() -> Self {
        Self {
            semantic_weight: 0.5,
            bm25_weight: 0.3,
            entity_boost_weight: 0.2,
            default_top_k: 20,
            default_threshold: 0.1,
        }
    }
}

impl AppConfig {
    pub fn load() -> Result<Self, figment::Error> {
        Figment::new()
            .merge(Toml::file("config.toml"))
            .merge(Env::prefixed("UMBRA_").split("__"))
            .extract()
    }
}
