use super::{SegmentId, CommitEpoch, Value};
use std::collections::HashMap;
use serde::{Deserialize, Serialize, Deserializer, Serializer};
use roaring::RoaringBitmap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ColumnStats {
    pub min_value: Option<Vec<u8>>,
    pub max_value: Option<Vec<u8>>,
    pub null_count: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ZoneMap {
    pub min_value: Option<Value>,
    pub max_value: Option<Value>,
    pub null_count: u64,
}

impl ZoneMap {
    pub fn new() -> Self {
        Self {
            min_value: None,
            max_value: None,
            null_count: 0,
        }
    }
    
    pub fn update_with_value(&mut self, value: &Value) {
        if matches!(value, Value::Null) {
            self.null_count += 1;
            return;
        }
        
        // Update min value
        match &self.min_value {
            None => self.min_value = Some(value.clone()),
            Some(current_min) => {
                if value_lt(value, current_min) {
                    self.min_value = Some(value.clone());
                }
            }
        }
        
        // Update max value
        match &self.max_value {
            None => self.max_value = Some(value.clone()),
            Some(current_max) => {
                if value_gt(value, current_max) {
                    self.max_value = Some(value.clone());
                }
            }
        }
    }
    
    pub fn might_contain_value(&self, value: &Value) -> bool {
        // NULL values are always possible
        if matches!(value, Value::Null) {
            return self.null_count > 0;
        }
        
        // Check if value is within min/max range
        match (&self.min_value, &self.max_value) {
            (Some(min), Some(max)) => {
                !value_lt(value, min) && !value_gt(value, max)
            }
            _ => true, // If we don't have bounds, assume it might contain the value
        }
    }
}

fn value_lt(a: &Value, b: &Value) -> bool {
    match (a, b) {
        (Value::Integer(a_val), Value::Integer(b_val)) => a_val < b_val,
        (Value::Text(a_val), Value::Text(b_val)) => a_val < b_val,
        (Value::Float(a_val), Value::Float(b_val)) => a_val < b_val,
        (Value::Boolean(a_val), Value::Boolean(b_val)) => !a_val && *b_val,
        _ => false, // Different types, can't compare
    }
}

fn value_gt(a: &Value, b: &Value) -> bool {
    match (a, b) {
        (Value::Integer(a_val), Value::Integer(b_val)) => a_val > b_val,
        (Value::Text(a_val), Value::Text(b_val)) => a_val > b_val,
        (Value::Float(a_val), Value::Float(b_val)) => a_val > b_val,
        (Value::Boolean(a_val), Value::Boolean(b_val)) => *a_val && !b_val,
        _ => false, // Different types, can't compare
    }
}

#[derive(Debug, Clone)]
pub struct BloomFilter {
    pub bitmap: RoaringBitmap,
    pub num_hashes: u32,
    pub num_items: u64,
}

// Custom serialization for BloomFilter
impl Serialize for BloomFilter {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        use serde::ser::SerializeStruct;
        let mut state = serializer.serialize_struct("BloomFilter", 3)?;
        state.serialize_field("num_hashes", &self.num_hashes)?;
        state.serialize_field("num_items", &self.num_items)?;
        
        // Serialize the bitmap as a Vec<u32>
        let values: Vec<u32> = self.bitmap.iter().collect();
        state.serialize_field("bitmap_values", &values)?;
        state.end()
    }
}

// Custom deserialization for BloomFilter
impl<'de> Deserialize<'de> for BloomFilter {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        use serde::de::{self, MapAccess, Visitor};
        use std::fmt;
        
        #[derive(Deserialize)]
        #[serde(field_identifier, rename_all = "lowercase")]
        enum Field { NumHashes, NumItems, BitmapValues }
        
        struct BloomFilterVisitor;
        
        impl<'de> Visitor<'de> for BloomFilterVisitor {
            type Value = BloomFilter;
            
            fn expecting(&self, formatter: &mut fmt::Formatter) -> fmt::Result {
                formatter.write_str("struct BloomFilter")
            }
            
            fn visit_map<V>(self, mut map: V) -> Result<BloomFilter, V::Error>
            where
                V: MapAccess<'de>,
            {
                let mut num_hashes = None;
                let mut num_items = None;
                let mut bitmap_values = None;
                
                while let Some(key) = map.next_key()? {
                    match key {
                        Field::NumHashes => {
                            if num_hashes.is_some() {
                                return Err(de::Error::duplicate_field("num_hashes"));
                            }
                            num_hashes = Some(map.next_value()?);
                        }
                        Field::NumItems => {
                            if num_items.is_some() {
                                return Err(de::Error::duplicate_field("num_items"));
                            }
                            num_items = Some(map.next_value()?);
                        }
                        Field::BitmapValues => {
                            if bitmap_values.is_some() {
                                return Err(de::Error::duplicate_field("bitmap_values"));
                            }
                            bitmap_values = Some(map.next_value()?);
                        }
                    }
                }
                
                let num_hashes = num_hashes.ok_or_else(|| de::Error::missing_field("num_hashes"))?;
                let num_items = num_items.ok_or_else(|| de::Error::missing_field("num_items"))?;
                let bitmap_values: Vec<u32> = bitmap_values.ok_or_else(|| de::Error::missing_field("bitmap_values"))?;
                
                let mut bitmap = RoaringBitmap::new();
                for value in bitmap_values {
                    bitmap.insert(value);
                }
                
                Ok(BloomFilter {
                    bitmap,
                    num_hashes,
                    num_items,
                })
            }
        }
        
        const FIELDS: &[&str] = &["num_hashes", "num_items", "bitmap_values"];
        deserializer.deserialize_struct("BloomFilter", FIELDS, BloomFilterVisitor)
    }
}

impl BloomFilter {
    pub fn new(expected_items: u64) -> Self {
        // Calculate optimal number of hash functions
        let num_hashes = Self::optimal_num_hashes(expected_items);
        
        Self {
            bitmap: RoaringBitmap::new(),
            num_hashes,
            num_items: expected_items,
        }
    }
    
    fn optimal_num_hashes(expected_items: u64) -> u32 {
        // For a fixed false positive rate, optimal k = (m/n) * ln(2)
        // We'll use a simple heuristic
        if expected_items == 0 {
            3
        } else {
            (expected_items as f64).ln() as u32 + 1
        }
    }
    
    pub fn add(&mut self, value: &Value) {
        let hash_values = self.hash_value(value);
        
        for hash in hash_values {
            self.bitmap.insert(hash);
        }
    }
    
    pub fn might_contain(&self, value: &Value) -> bool {
        let hash_values = self.hash_value(value);
        
        for hash in hash_values {
            if !self.bitmap.contains(hash) {
                return false;
            }
        }
        true
    }
    
    fn hash_value(&self, value: &Value) -> Vec<u32> {
        let bytes = match value {
            Value::Integer(i) => i.to_le_bytes().to_vec(),
            Value::Text(s) => s.as_bytes().to_vec(),
            Value::Boolean(b) => vec![if *b { 1 } else { 0 }],
            Value::Float(f) => f.to_le_bytes().to_vec(),
            Value::Null => vec![0],
        };
        
        let mut hashes = Vec::with_capacity(self.num_hashes as usize);
        
        // Use double hashing to generate multiple hash values
        let hash1 = crc32fast::hash(&bytes);
        let hash2 = xxhash_rust::xxh3::xxh3_64(&bytes) as u32;
        
        for i in 0..self.num_hashes {
            let hash = hash1.wrapping_add(i.wrapping_mul(hash2)) % (1u32 << 31);
            hashes.push(hash);
        }
        
        hashes
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SegmentMeta {
    pub id: SegmentId,
    pub rows: u64,
    pub stats: HashMap<String, ColumnStats>, // column_name -> stats
    pub commit_epoch: CommitEpoch,
    pub file_path: String,
    pub compression: super::CompressionType,
    pub zone_maps: HashMap<String, ZoneMap>, // column_name -> zone map
    pub bloom_filters: HashMap<String, BloomFilter>, // column_name -> bloom filter
}

#[derive(Debug, Serialize, Deserialize)]
pub struct Segment {
    pub meta: SegmentMeta,
    // In a real implementation, this would contain file handles or mmap
}

impl Segment {
    pub fn new(
        id: SegmentId,
        rows: u64,
        stats: HashMap<String, ColumnStats>,
        commit_epoch: CommitEpoch,
        file_path: String,
        compression: super::CompressionType,
        zone_maps: HashMap<String, ZoneMap>,
        bloom_filters: HashMap<String, BloomFilter>,
    ) -> Self {
        Self {
            meta: SegmentMeta {
                id,
                rows,
                stats,
                commit_epoch,
                file_path,
                compression,
                zone_maps,
                bloom_filters,
            },
        }
    }
    
    pub fn might_contain_value(&self, column_name: &str, value: &Value) -> bool {
        // Check zone map first (min/max pruning)
        if let Some(zone_map) = self.meta.zone_maps.get(column_name) {
            if !zone_map.might_contain_value(value) {
                return false;
            }
        }
        
        // Check bloom filter
        if let Some(bloom_filter) = self.meta.bloom_filters.get(column_name) {
            bloom_filter.might_contain(value)
        } else {
            // If no bloom filter, we can't prune
            true
        }
    }
}