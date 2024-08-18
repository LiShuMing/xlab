pub mod catalog;
pub mod segment;
pub mod manifest;
pub mod txn;
pub mod compaction;
pub mod delete_vector;
pub mod object_store;
pub mod column_reader;
pub mod index;

use std::sync::Arc;
use tokio::sync::RwLock;
use uuid::Uuid;

pub type CommitEpoch = u64;
pub type SegmentId = Uuid;

// Move these definitions to the storage module level
#[derive(Debug, Clone, PartialEq, Eq, Hash, serde::Serialize, serde::Deserialize)]
pub enum DataType {
    Integer,
    Text,
    Boolean,
    Float,
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub enum Value {
    Integer(i64),
    Text(String),
    Boolean(bool),
    Float(f64),
    Null,
}

// Implement PartialEq manually for Value to handle f64 comparison
impl PartialEq for Value {
    fn eq(&self, other: &Self) -> bool {
        match (self, other) {
            (Value::Integer(a), Value::Integer(b)) => a == b,
            (Value::Text(a), Value::Text(b)) => a == b,
            (Value::Boolean(a), Value::Boolean(b)) => a == b,
            (Value::Float(a), Value::Float(b)) => a.to_bits() == b.to_bits(), // Handle NaN correctly
            (Value::Null, Value::Null) => true,
            _ => false,
        }
    }
}

// Implement Eq for Value
impl Eq for Value {}

// Implement Hash for Value
impl std::hash::Hash for Value {
    fn hash<H: std::hash::Hasher>(&self, state: &mut H) {
        match self {
            Value::Integer(i) => i.hash(state),
            Value::Text(s) => s.hash(state),
            Value::Boolean(b) => b.hash(state),
            Value::Float(f) => f.to_bits().hash(state), // Handle NaN correctly
            Value::Null => 0.hash(state),
        }
    }
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct ColumnDef {
    pub name: String,
    pub data_type: DataType,
    pub nullable: bool,
}

pub use catalog::{Catalog, Table};
pub use segment::{Segment, SegmentMeta, ColumnStats, ZoneMap, BloomFilter};
pub use delete_vector::{DeleteVector, DeleteVectorRef};
pub use manifest::{Manifest, Snapshot};
pub use txn::{Txn, TxnManager, ProvisionalObj};
pub use object_store::{ObjectStore, LocalFileSystemStore};
pub use column_reader::ColumnReader;
pub use compaction::run_once as run_compaction;
pub use index::PrimaryKeyIndex;

// Compression type definition
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub enum CompressionType {
    None,
    Zstd,
    Lz4,
}

impl CompressionType {
    pub fn compress(&self, data: &[u8]) -> Result<Vec<u8>, String> {
        match self {
            CompressionType::None => Ok(data.to_vec()),
            CompressionType::Zstd => {
                zstd::encode_all(data, 3)
                    .map_err(|e| format!("Zstd compression error: {}", e))
            }
            CompressionType::Lz4 => {
                Ok(lz4_flex::compress_prepend_size(data))
            }
        }
    }
    
    pub fn decompress(&self, data: &[u8]) -> Result<Vec<u8>, String> {
        match self {
            CompressionType::None => Ok(data.to_vec()),
            CompressionType::Zstd => {
                zstd::decode_all(data)
                    .map_err(|e| format!("Zstd decompression error: {}", e))
            }
            CompressionType::Lz4 => {
                lz4_flex::decompress_size_prepended(data)
                    .map_err(|e| format!("LZ4 decompression error: {}", e))
            }
        }
    }
}

impl Value {
    pub fn data_type(&self) -> DataType {
        match self {
            Value::Integer(_) => DataType::Integer,
            Value::Text(_) => DataType::Text,
            Value::Boolean(_) => DataType::Boolean,
            Value::Float(_) => DataType::Float,
            Value::Null => panic!("Null value has no type"),
        }
    }
    
    pub fn to_bytes(&self) -> Vec<u8> {
        match self {
            Value::Integer(i) => i.to_le_bytes().to_vec(),
            Value::Text(s) => s.clone().into_bytes(),
            Value::Boolean(b) => vec![if *b { 1 } else { 0 }],
            Value::Float(f) => f.to_le_bytes().to_vec(),
            Value::Null => vec![],
        }
    }
    
    pub fn from_bytes(data_type: &DataType, bytes: &[u8]) -> Self {
        match data_type {
            DataType::Integer => {
                let mut array = [0; 8];
                array.copy_from_slice(bytes);
                Value::Integer(i64::from_le_bytes(array))
            }
            DataType::Text => Value::Text(String::from_utf8_lossy(bytes).to_string()),
            DataType::Boolean => Value::Boolean(bytes[0] != 0),
            DataType::Float => {
                let mut array = [0; 8];
                array.copy_from_slice(bytes);
                Value::Float(f64::from_le_bytes(array))
            }
        }
    }
}

pub struct StorageEngine {
    pub catalog: Arc<RwLock<Catalog>>,
    pub manifest: Arc<RwLock<Manifest>>,
    pub txn_manager: Arc<TxnManager>,
    // Note: We can't derive Debug for object_store because dyn ObjectStore doesn't implement Debug
    // We'll implement Debug manually if needed
    pub object_store: Arc<dyn ObjectStore>,
    pub base_path: String,
}

impl StorageEngine {
    pub async fn new(object_store: Arc<dyn ObjectStore>, base_path: String) -> Result<Self, String> {
        let catalog = Arc::new(RwLock::new(Catalog::new(base_path.clone())));
        let manifest = Arc::new(RwLock::new(Manifest::new()));
        let txn_manager = Arc::new(TxnManager::new());
        
        // Create the base directory if it doesn't exist
        tokio::fs::create_dir_all(&base_path)
            .await
            .map_err(|e| format!("Failed to create base directory: {}", e))?;
        
        Ok(Self {
            catalog,
            manifest,
            txn_manager,
            object_store,
            base_path,
        })
    }
    
    pub async fn begin_txn(&self) -> Result<Txn, String> {
        self.txn_manager.begin_txn().await
    }
    
    pub async fn commit_txn(&self, txn: Txn) -> Result<(), String> {
        self.txn_manager.commit_txn(txn).await
    }
    
    pub async fn create_table(&self, name: String, columns: Vec<ColumnDef>) -> Result<(), String> {
        let mut catalog = self.catalog.write().await;
        catalog.create_table(name, columns).await
    }
    
    pub async fn insert_row(&self, table_name: &str, values: Vec<Value>) -> Result<(), String> {
        let mut catalog = self.catalog.write().await;
        catalog.insert_row(table_name, values).await
    }
    
    pub async fn scan_table(&self, table_name: &str) -> Result<TableScan, String> {
        let mut catalog = self.catalog.write().await;
        catalog.scan_table(table_name).await
    }
    
    pub async fn get_table_columns(&self, table_name: &str) -> Result<Vec<ColumnDef>, String> {
        let catalog = self.catalog.read().await;
        catalog.get_table_columns(table_name)
    }
    
    pub async fn flush(&self) -> Result<(), String> {
        let mut catalog = self.catalog.write().await;
        let table_names: Vec<String> = catalog.tables.keys().cloned().collect();
        
        for table_name in table_names {
            catalog.flush_table_segment(&table_name).await?;
        }
        
        Ok(())
    }
}

// Implement Debug manually for StorageEngine
impl std::fmt::Debug for StorageEngine {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.debug_struct("StorageEngine")
            .field("catalog", &self.catalog)
            .field("manifest", &self.manifest)
            .field("txn_manager", &self.txn_manager)
            .field("object_store", &"dyn ObjectStore")
            .field("base_path", &self.base_path)
            .finish()
    }
}

impl Drop for StorageEngine {
    fn drop(&mut self) {
        // In a real implementation, we would flush all pending data to disk
        // This is a simplified implementation since we can't easily async drop
    }
}

pub struct TableScan {
    rows: Vec<Vec<Value>>,
    current_index: usize,
}

impl TableScan {
    pub fn new(rows: Vec<Vec<Value>>) -> Self {
        Self {
            rows,
            current_index: 0,
        }
    }
    
    pub async fn next_batch(&mut self, batch_size: usize) -> Option<Vec<Vec<Value>>> {
        if self.current_index >= self.rows.len() {
            return None;
        }
        
        let end_index = std::cmp::min(self.current_index + batch_size, self.rows.len());
        let batch = self.rows[self.current_index..end_index].to_vec();
        self.current_index = end_index;
        
        Some(batch)
    }
    
    pub fn has_more(&self) -> bool {
        self.current_index < self.rows.len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Arc;
    
    #[tokio::test]
    async fn test_storage_engine_creation() {
        let object_store = Arc::new(LocalFileSystemStore::new("/tmp/rdb_test".to_string()));
        let engine = StorageEngine::new(object_store, "/tmp/rdb_test".to_string()).await;
        assert!(engine.is_ok());
    }
    
    #[tokio::test]
    async fn test_create_table() {
        let test_dir = "/tmp/rdb_test_create_table";
        let object_store = Arc::new(LocalFileSystemStore::new(test_dir.to_string()));
        let engine = StorageEngine::new(object_store, test_dir.to_string()).await.unwrap();
        
        let columns = vec![
            ColumnDef {
                name: "id".to_string(),
                data_type: DataType::Integer,
                nullable: false,
            },
            ColumnDef {
                name: "name".to_string(),
                data_type: DataType::Text,
                nullable: true,
            }
        ];
        
        let result = engine.create_table("users".to_string(), columns).await;
        assert!(result.is_ok());
    }
    
    #[tokio::test]
    async fn test_begin_txn() {
        let test_dir = "/tmp/rdb_test_begin_txn";
        let object_store = Arc::new(LocalFileSystemStore::new(test_dir.to_string()));
        let engine = StorageEngine::new(object_store, test_dir.to_string()).await.unwrap();
        
        let txn = engine.begin_txn().await;
        assert!(txn.is_ok());
    }
    
    #[tokio::test]
    async fn test_insert_and_scan() {
        let test_dir = "/tmp/rdb_test_insert_scan";
        // Clean up test directory
        let _ = tokio::fs::remove_dir_all(test_dir).await;
        
        let object_store = Arc::new(LocalFileSystemStore::new(test_dir.to_string()));
        let engine = StorageEngine::new(object_store, test_dir.to_string()).await.unwrap();
        
        // Create a table
        let columns = vec![
            ColumnDef {
                name: "id".to_string(),
                data_type: DataType::Integer,
                nullable: false,
            },
            ColumnDef {
                name: "name".to_string(),
                data_type: DataType::Text,
                nullable: true,
            }
        ];
        
        let result = engine.create_table("users".to_string(), columns).await;
        assert!(result.is_ok());
        
        // Insert a row
        let values = vec![
            Value::Integer(1),
            Value::Text("Alice".to_string()),
        ];
        
        let result = engine.insert_row("users", values).await;
        assert!(result.is_ok());
        
        // Flush the data to disk
        let result = engine.flush().await;
        assert!(result.is_ok());
        
        // Scan the table
        let mut scan = engine.scan_table("users").await.unwrap();
        let batch = scan.next_batch(10).await;
        assert!(batch.is_some());
        let rows = batch.unwrap();
        assert_eq!(rows.len(), 1);
        assert_eq!(rows[0][0], Value::Integer(1));
        assert_eq!(rows[0][1], Value::Text("Alice".to_string()));
    }
}