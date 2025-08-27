use super::{SegmentMeta, DeleteVector, SegmentId, CommitEpoch, Value, DataType, ColumnDef, ZoneMap, BloomFilter, PrimaryKeyIndex};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TableSchema {
    pub name: String,
    pub columns: Vec<ColumnDef>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct TableMetadata {
    pub schema: TableSchema,
    pub segments: Vec<SegmentMeta>,
    pub delete_vectors: Vec<DeleteVector>,
}

#[derive(Debug)]
pub struct Table {
    pub name: String,
    pub columns: Vec<ColumnDef>,
    pub segments: Vec<SegmentMeta>,
    pub delete_vectors: Vec<DeleteVector>,
    pub rows: Vec<Vec<Value>>, // In-memory cache of recent rows
    pub compression: super::CompressionType,
    pub primary_key_index: Option<PrimaryKeyIndex>,
}

impl Table {
    pub fn new(name: String, columns: Vec<ColumnDef>) -> Self {
        Self {
            name: name.clone(),
            columns,
            segments: Vec::new(),
            delete_vectors: Vec::new(),
            rows: Vec::new(),
            compression: super::CompressionType::Zstd, // Default to Zstd compression
            primary_key_index: None,
        }
    }
    
    pub fn to_metadata(&self) -> TableMetadata {
        TableMetadata {
            schema: TableSchema {
                name: self.name.clone(),
                columns: self.columns.clone(),
            },
            segments: self.segments.clone(),
            delete_vectors: self.delete_vectors.clone(),
        }
    }
    
    pub fn from_metadata(metadata: TableMetadata) -> Self {
        Self {
            name: metadata.schema.name,
            columns: metadata.schema.columns,
            segments: metadata.segments,
            delete_vectors: metadata.delete_vectors,
            rows: Vec::new(), // Start with empty cache
            compression: super::CompressionType::Zstd, // Default compression
            primary_key_index: None,
        }
    }
}

#[derive(Debug)]
pub struct Catalog {
    pub tables: HashMap<String, Table>,
    pub base_path: String,
}

impl Catalog {
    pub fn new(base_path: String) -> Self {
        Self {
            tables: HashMap::new(),
            base_path,
        }
    }
    
    pub fn get_table_path(&self, table_name: &str) -> String {
        format!("{}/{}.table", self.base_path, table_name)
    }
    
    pub fn get_segment_path(&self, table_name: &str, segment_id: &SegmentId) -> String {
        format!("{}/segments/{}.{}.segment", self.base_path, table_name, segment_id)
    }
    
    pub fn get_column_path(&self, table_name: &str, segment_id: &SegmentId, column_name: &str) -> String {
        format!("{}/segments/{}.{}.{}.column", self.base_path, table_name, segment_id, column_name)
    }
    
    pub async fn load_table(&mut self, table_name: &str) -> Result<(), String> {
        if self.tables.contains_key(table_name) {
            return Ok(());
        }
        
        let table_path = self.get_table_path(table_name);
        match tokio::fs::read(&table_path).await {
            Ok(data) => {
                let metadata: TableMetadata = bincode::deserialize(&data)
                    .map_err(|e| format!("Failed to deserialize table metadata: {}", e))?;
                let table = Table::from_metadata(metadata);
                self.tables.insert(table_name.to_string(), table);
                Ok(())
            }
            Err(_) => {
                // Table file doesn't exist, which is fine for new tables
                Err(format!("Table {} not found", table_name))
            }
        }
    }
    
    pub async fn save_table(&self, table_name: &str) -> Result<(), String> {
        if let Some(table) = self.tables.get(table_name) {
            let metadata = table.to_metadata();
            let serialized = bincode::serialize(&metadata)
                .map_err(|e| format!("Failed to serialize table metadata: {}", e))?;
            
            let table_path = self.get_table_path(table_name);
            // Create directory if it doesn't exist
            if let Some(parent) = std::path::Path::new(&table_path).parent() {
                tokio::fs::create_dir_all(parent)
                    .await
                    .map_err(|e| format!("Failed to create directories: {}", e))?;
            }
            
            tokio::fs::write(&table_path, serialized)
                .await
                .map_err(|e| format!("Failed to write table metadata: {}", e))?;
        }
        Ok(())
    }
    
    pub async fn create_table(&mut self, name: String, columns: Vec<ColumnDef>) -> Result<(), String> {
        if self.tables.contains_key(&name) {
            return Err(format!("Table {} already exists", name));
        }
        
        let table = Table::new(name.clone(), columns);
        self.tables.insert(name.clone(), table);
        
        // Save the table metadata to disk
        self.save_table(&name).await?;
        Ok(())
    }
    
    pub async fn insert_row(&mut self, table_name: &str, values: Vec<Value>) -> Result<(), String> {
        // Load table if not already loaded
        if !self.tables.contains_key(table_name) {
            self.load_table(table_name).await.or_else(|_| {
                Err(format!("Table {} does not exist", table_name))
            })?;
        }
        
        let table = self.tables.get_mut(table_name)
            .ok_or_else(|| format!("Table {} does not exist", table_name))?;
        
        // Validate the number of values matches the number of columns
        if values.len() != table.columns.len() {
            return Err(format!(
                "Expected {} values, but got {}",
                table.columns.len(),
                values.len()
            ));
        }
        
        // Validate data types
        for (i, (value, column)) in values.iter().zip(table.columns.iter()).enumerate() {
            if !value_matches_type(value, &column.data_type) {
                return Err(format!(
                    "Value at position {} does not match column {}'s type",
                    i, column.name
                ));
            }
        }
        
        table.rows.push(values);
        
        // If we have enough rows, flush to a segment
        if table.rows.len() >= 1000 { // Flush every 1000 rows
            let table_name_clone = table_name.to_string();
            self.flush_table_segment(&table_name_clone).await?;
        }
        
        Ok(())
    }
    
    pub async fn flush_table_segment(&mut self, table_name: &str) -> Result<(), String> {
        // Clone the data we need to avoid borrowing issues
        let segment_data = {
            let table = self.tables.get(table_name)
                .ok_or_else(|| format!("Table {} not found", table_name))?;
            
            if table.rows.is_empty() {
                return Ok(());
            }
            
            // Create a new segment
            let segment_id = Uuid::new_v4();
            let row_count = table.rows.len() as u64;
            
            // Create columnar storage and build indexes
            let mut columns_data: HashMap<String, Vec<Value>> = HashMap::new();
            let mut zone_maps: HashMap<String, ZoneMap> = HashMap::new();
            let mut bloom_filters: HashMap<String, BloomFilter> = HashMap::new();
            
            for (i, column) in table.columns.iter().enumerate() {
                let mut column_data = Vec::new();
                let mut zone_map = ZoneMap::new();
                let mut bloom_filter = BloomFilter::new(row_count);
                
                for row in &table.rows {
                    let value = &row[i];
                    column_data.push(value.clone());
                    zone_map.update_with_value(value);
                    bloom_filter.add(value);
                }
                
                columns_data.insert(column.name.clone(), column_data);
                zone_maps.insert(column.name.clone(), zone_map);
                bloom_filters.insert(column.name.clone(), bloom_filter);
            }
            
            // Calculate statistics for each column
            let mut stats = HashMap::new();
            for (column_name, column_data) in &columns_data {
                let column_stats = calculate_column_stats(column_data);
                stats.insert(column_name.clone(), column_stats);
            }
            
            // Create segment metadata
            let segment_meta = super::Segment::new(
                segment_id,
                row_count,
                stats,
                0, // commit_epoch
                format!("{}/segments/{}.{}.segment", self.base_path, table_name, segment_id),
                table.compression.clone(),
                zone_maps,
                bloom_filters,
            ).meta;
            
            Some((segment_id, segment_meta, columns_data, table.compression.clone()))
        };
        
        if let Some((segment_id, segment_meta, columns_data, compression)) = segment_data {
            // Save each column to disk
            for (column_name, column_data) in columns_data {
                self.save_column_data(table_name, &segment_id, &column_name, &column_data, &compression).await?;
            }
            
            // Save segment metadata
            self.save_segment_metadata(&segment_meta).await?;
            
            // Update the table with the new segment
            if let Some(table) = self.tables.get_mut(table_name) {
                table.segments.push(segment_meta);
                table.rows.clear(); // Clear in-memory rows
            }
            
            // Save updated table metadata
            self.save_table(table_name).await?;
        }
        
        Ok(())
    }
    
    async fn save_column_data(
        &self,
        table_name: &str,
        segment_id: &SegmentId,
        column_name: &str,
        column_data: &[Value],
        compression: &super::CompressionType,
    ) -> Result<(), String> {
        // Serialize column data
        let serialized = bincode::serialize(column_data)
            .map_err(|e| format!("Failed to serialize column data: {}", e))?;
        
        // Compress data
        let compressed = compression.compress(&serialized)?;
        
        // Save to disk
        let column_path = self.get_column_path(table_name, segment_id, column_name);
        if let Some(parent) = std::path::Path::new(&column_path).parent() {
            tokio::fs::create_dir_all(parent)
                .await
                .map_err(|e| format!("Failed to create directories: {}", e))?;
        }
        
        tokio::fs::write(&column_path, compressed)
            .await
            .map_err(|e| format!("Failed to write column data: {}", e))?;
        
        Ok(())
    }
    
    async fn save_segment_metadata(&self, segment_meta: &SegmentMeta) -> Result<(), String> {
        let serialized = bincode::serialize(segment_meta)
            .map_err(|e| format!("Failed to serialize segment metadata: {}", e))?;
        
        let segment_path = segment_meta.file_path.clone();
        if let Some(parent) = std::path::Path::new(&segment_path).parent() {
            tokio::fs::create_dir_all(parent)
                .await
                .map_err(|e| format!("Failed to create directories: {}", e))?;
        }
        
        tokio::fs::write(&segment_path, serialized)
            .await
            .map_err(|e| format!("Failed to write segment metadata: {}", e))?;
        
        Ok(())
    }
    
    pub async fn load_table_data(&mut self, table_name: &str) -> Result<Vec<Vec<Value>>, String> {
        // Load table if not already loaded
        if !self.tables.contains_key(table_name) {
            self.load_table(table_name).await?;
        }
        
        let table = self.tables.get(table_name)
            .ok_or_else(|| format!("Table {} not found", table_name))?;
        
        let mut all_rows = Vec::new();
        
        // Load data from segments
        for segment_meta in &table.segments {
            let segment_rows = self.load_segment_data(table_name, segment_meta).await?;
            all_rows.extend(segment_rows);
        }
        
        // Add in-memory rows
        if let Some(table) = self.tables.get(table_name) {
            all_rows.extend(table.rows.clone());
        }
        
        Ok(all_rows)
    }
    
    async fn load_segment_data(&self, table_name: &str, segment_meta: &SegmentMeta) -> Result<Vec<Vec<Value>>, String> {
        let table = self.tables.get(table_name)
            .ok_or_else(|| format!("Table {} not found", table_name))?;
        
        let mut columns_data: Vec<Vec<Value>> = Vec::new();
        
        // Load each column
        for column in &table.columns {
            let column_path = self.get_column_path(table_name, &segment_meta.id, &column.name);
            match tokio::fs::read(&column_path).await {
                Ok(compressed_data) => {
                    // Decompress data
                    let serialized_data = segment_meta.compression.decompress(&compressed_data)?;
                    
                    // Deserialize column data
                    let column_data: Vec<Value> = bincode::deserialize(&serialized_data)
                        .map_err(|e| format!("Failed to deserialize column data: {}", e))?;
                    
                    columns_data.push(column_data);
                }
                Err(_) => {
                    // Column file doesn't exist, create empty column
                    columns_data.push(Vec::new());
                }
            }
        }
        
        // Transform columnar data to row-based data
        let mut rows = Vec::new();
        if !columns_data.is_empty() {
            let row_count = columns_data.iter().map(|c| c.len()).max().unwrap_or(0);
            for i in 0..row_count {
                let mut row = Vec::new();
                for column_data in &columns_data {
                    if i < column_data.len() {
                        row.push(column_data[i].clone());
                    } else {
                        row.push(Value::Null);
                    }
                }
                rows.push(row);
            }
        }
        
        Ok(rows)
    }
    
    pub async fn scan_table(&mut self, table_name: &str) -> Result<super::TableScan, String> {
        // Load table if not already loaded
        if !self.tables.contains_key(table_name) {
            self.load_table(table_name).await.or_else(|_| {
                Err(format!("Table {} does not exist", table_name))
            })?;
        }
        
        // Load table data
        let rows = self.load_table_data(table_name).await?;
        
        Ok(super::TableScan::new(rows))
    }
    
    pub fn get_table_columns(&self, table_name: &str) -> Result<Vec<ColumnDef>, String> {
        let table = self.tables.get(table_name)
            .ok_or_else(|| format!("Table {} does not exist", table_name))?;
        Ok(table.columns.clone())
    }
}

fn calculate_column_stats(column_data: &[Value]) -> super::ColumnStats {
    // This is a simplified implementation
    // In a real implementation, we would calculate proper min/max values
    super::ColumnStats {
        min_value: None,
        max_value: None,
        null_count: column_data.iter().filter(|v| matches!(v, Value::Null)).count() as u64,
    }
}

fn value_matches_type(value: &Value, data_type: &DataType) -> bool {
    match (value, data_type) {
        (Value::Integer(_), DataType::Integer) => true,
        (Value::Text(_), DataType::Text) => true,
        (Value::Boolean(_), DataType::Boolean) => true,
        (Value::Float(_), DataType::Float) => true,
        (Value::Null, _) => true, // NULL is allowed for any column
        _ => false,
    }
}