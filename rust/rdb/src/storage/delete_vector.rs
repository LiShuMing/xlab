use super::{SegmentId, CommitEpoch};
use roaring::RoaringBitmap;
use std::sync::Arc;
use serde::{Deserialize, Deserializer, Serialize, Serializer};

#[derive(Debug, Clone)]
pub struct DeleteVector {
    pub seg: SegmentId,
    pub commit_epoch: CommitEpoch,
    pub bitmap: RoaringBitmap,
}

// Custom serialization for DeleteVector
impl Serialize for DeleteVector {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        use serde::ser::SerializeStruct;
        let mut state = serializer.serialize_struct("DeleteVector", 3)?;
        state.serialize_field("seg", &self.seg)?;
        state.serialize_field("commit_epoch", &self.commit_epoch)?;
        
        // Serialize the bitmap as a Vec<u32>
        let values: Vec<u32> = self.bitmap.iter().collect();
        state.serialize_field("bitmap_values", &values)?;
        state.end()
    }
}

// Custom deserialization for DeleteVector
impl<'de> Deserialize<'de> for DeleteVector {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        use serde::de::{self, MapAccess, Visitor};
        use std::fmt;
        
        #[derive(Deserialize)]
        #[serde(field_identifier, rename_all = "lowercase")]
        enum Field { Seg, CommitEpoch, BitmapValues }
        
        struct DeleteVectorVisitor;
        
        impl<'de> Visitor<'de> for DeleteVectorVisitor {
            type Value = DeleteVector;
            
            fn expecting(&self, formatter: &mut fmt::Formatter) -> fmt::Result {
                formatter.write_str("struct DeleteVector")
            }
            
            fn visit_map<V>(self, mut map: V) -> Result<DeleteVector, V::Error>
            where
                V: MapAccess<'de>,
            {
                let mut seg = None;
                let mut commit_epoch = None;
                let mut bitmap_values = None;
                
                while let Some(key) = map.next_key()? {
                    match key {
                        Field::Seg => {
                            if seg.is_some() {
                                return Err(de::Error::duplicate_field("seg"));
                            }
                            seg = Some(map.next_value()?);
                        }
                        Field::CommitEpoch => {
                            if commit_epoch.is_some() {
                                return Err(de::Error::duplicate_field("commit_epoch"));
                            }
                            commit_epoch = Some(map.next_value()?);
                        }
                        Field::BitmapValues => {
                            if bitmap_values.is_some() {
                                return Err(de::Error::duplicate_field("bitmap_values"));
                            }
                            bitmap_values = Some(map.next_value()?);
                        }
                    }
                }
                
                let seg = seg.ok_or_else(|| de::Error::missing_field("seg"))?;
                let commit_epoch = commit_epoch.ok_or_else(|| de::Error::missing_field("commit_epoch"))?;
                let bitmap_values: Vec<u32> = bitmap_values.ok_or_else(|| de::Error::missing_field("bitmap_values"))?;
                
                let mut bitmap = RoaringBitmap::new();
                for value in bitmap_values {
                    bitmap.insert(value);
                }
                
                Ok(DeleteVector {
                    seg,
                    commit_epoch,
                    bitmap,
                })
            }
        }
        
        const FIELDS: &[&str] = &["seg", "commit_epoch", "bitmap_values"];
        deserializer.deserialize_struct("DeleteVector", FIELDS, DeleteVectorVisitor)
    }
}

pub type DeleteVectorRef = Arc<DeleteVector>;

impl DeleteVector {
    pub fn new(seg: SegmentId, commit_epoch: CommitEpoch) -> Self {
        Self {
            seg,
            commit_epoch,
            bitmap: RoaringBitmap::new(),
        }
    }
    
    pub fn add_deleted_row(&mut self, row_id: u32) {
        self.bitmap.insert(row_id);
    }
    
    pub fn is_deleted(&self, row_id: u32) -> bool {
        self.bitmap.contains(row_id)
    }
}