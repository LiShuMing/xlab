use lance::dataset::Dataset as LanceDataset;
use std::collections::HashMap;
use std::sync::Arc;

use crate::UmbraResult;

pub mod catalog;
pub mod scan;
pub mod write;

/// Storage configuration.
#[derive(Debug, Clone)]
pub struct StorageConfig {
    pub base_path: String,
}

/// Manages Lance datasets and Iceberg catalog for the umbra tables.
pub struct StorageLayer {
    pub config: StorageConfig,
    /// Table name -> Dataset
    datasets: HashMap<String, Arc<LanceDataset>>,
}

pub const MEMORIES_TABLE: &str = "memories";
pub const ENTITIES_TABLE: &str = "entities";
pub const HISTORY_TABLE: &str = "history";
pub const MESSAGES_TABLE: &str = "messages";

impl StorageLayer {
    /// Create a new storage layer. Opens existing datasets or leaves empty
    /// for lazy creation on first write.
    pub async fn open(config: StorageConfig) -> UmbraResult<Self> {
        let mut datasets = HashMap::new();

        for name in &[MEMORIES_TABLE, ENTITIES_TABLE, HISTORY_TABLE, MESSAGES_TABLE] {
            let path = format!("{}/{}", &config.base_path, name);
            match LanceDataset::open(&path).await {
                Ok(ds) => {
                    tracing::info!("Opened existing table '{}' at {}", name, path);
                    datasets.insert(name.to_string(), Arc::new(ds));
                }
                Err(e) => {
                    tracing::warn!(
                        "Table '{}' at {} could not be opened: {e}. Will attempt creation on first write.",
                        name,
                        path
                    );
                }
            }
        }

        Ok(Self { config, datasets })
    }

    /// Get a reference to a dataset by name.
    pub fn get(&self, name: &str) -> Option<Arc<LanceDataset>> {
        self.datasets.get(name).cloned()
    }

    /// Remove a dataset from the cache (does not delete from disk).
    pub fn evict(&mut self, name: &str) {
        self.datasets.remove(name);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use arrow_array::{Int64Array, RecordBatch, StringArray};
    use arrow_schema::{DataType, Field, Schema};
    use std::sync::Arc;

    #[tokio::test]
    async fn test_storage_append_and_scan() {
        let tmp = tempfile::tempdir().unwrap();
        let config = StorageConfig {
            base_path: tmp.path().to_string_lossy().to_string(),
        };

        let mut layer = StorageLayer::open(config).await.unwrap();

        let schema = Arc::new(Schema::new(vec![
            Field::new("id", DataType::Utf8, false),
            Field::new("value", DataType::Int64, false),
        ]));

        let batch = RecordBatch::try_new(
            schema.clone(),
            vec![
                Arc::new(StringArray::from(vec!["a", "b", "c"])),
                Arc::new(Int64Array::from(vec![1, 2, 3])),
            ],
        )
        .unwrap();

        layer
            .append("test_table", batch, schema)
            .await
            .unwrap();

        let results = layer.scan_all("test_table", None).await.unwrap();
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].num_rows(), 3);
    }
}
