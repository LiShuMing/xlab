use std::collections::HashMap;
use std::sync::Mutex;
use serde::{Deserialize, Serialize};

/// Simplified iceberg catalog for MVP.
/// Stores table metadata in memory (no persistence between restarts).
#[derive(Debug, Default)]
pub struct MemoryCatalog {
    tables: Mutex<HashMap<String, TableMetadata>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TableMetadata {
    pub name: String,
    pub location: String,
    pub schema_json: String,
    pub current_snapshot_id: i64,
}

impl MemoryCatalog {
    pub fn new() -> Self {
        Self {
            tables: Mutex::new(HashMap::new()),
        }
    }

    pub fn register_table(&self, meta: TableMetadata) {
        let mut tables = self.tables.lock().expect("catalog lock poisoned");
        tables.insert(meta.name.clone(), meta);
    }

    pub fn get_table(&self, name: &str) -> Option<TableMetadata> {
        let tables = self.tables.lock().expect("catalog lock poisoned");
        tables.get(name).cloned()
    }

    pub fn list_tables(&self) -> Vec<String> {
        let tables = self.tables.lock().expect("catalog lock poisoned");
        tables.keys().cloned().collect()
    }
}
