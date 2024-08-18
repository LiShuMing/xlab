use arrow_array::{RecordBatch, RecordBatchIterator};
use arrow_schema::SchemaRef;
use lance::dataset::{Dataset, WriteMode, WriteParams};
use std::sync::Arc;

use crate::{UmbraError, UmbraResult};
use super::StorageLayer;

impl StorageLayer {
    /// Get or lazily create a Lance dataset for the named table.
    /// Returns the dataset (cached or newly created).
    pub async fn get_or_create(
        &mut self,
        name: &str,
        schema: &arrow_schema::Schema,
    ) -> UmbraResult<Arc<lance::dataset::Dataset>> {
        if let Some(ds) = self.datasets.get(name) {
            return Ok(Arc::clone(ds));
        }

        let path = format!("{}/{}", &self.config.base_path, name);
        std::fs::create_dir_all(&path).map_err(|e| {
            UmbraError::Storage(format!("create dir {path}: {e}"))
        })?;

        let schema_ref: SchemaRef = Arc::new(schema.clone());

        // Use Create mode to reject if already exists - prevents data loss.
        let empty_batch =
            RecordBatch::new_empty(schema_ref.clone());
        let reader = RecordBatchIterator::new(
            vec![Ok(empty_batch)].into_iter(),
            schema_ref,
        );

        let write_params = WriteParams {
            mode: WriteMode::Create,
            ..Default::default()
        };

        let ds = Dataset::write(reader, &path, Some(write_params))
            .await
            .map_err(|e| UmbraError::Storage(format!("create dataset {path}: {e}")))?;

        tracing::info!("Created table '{}' at {}", name, path);
        let ds = Arc::new(ds);
        self.datasets.insert(name.to_string(), Arc::clone(&ds));
        Ok(ds)
    }

    /// Append a batch to the named table.
    pub async fn append(
        &mut self,
        table_name: &str,
        batch: RecordBatch,
        schema: SchemaRef,
    ) -> UmbraResult<()> {
        self.get_or_create(table_name, &schema).await?;

        // Take the dataset out of the cache to get exclusive ownership
        // (Lance append requires &mut self).
        let ds = self.datasets.remove(table_name).ok_or_else(|| {
            UmbraError::Storage(format!("dataset {table_name} not found after creation"))
        })?;

        let mut ds = Arc::try_unwrap(ds)
            .map_err(|_| UmbraError::Storage(format!("dataset {table_name} still referenced")))?;

        let reader = RecordBatchIterator::new(
            vec![Ok(batch)].into_iter(),
            schema,
        );

        ds.append(reader, None).await.map_err(|e| {
            UmbraError::Storage(format!("append to {table_name}: {e}"))
        })?;

        self.datasets.insert(table_name.to_string(), Arc::new(ds));

        Ok(())
    }

    /// Append to memories table specifically.
    pub async fn append_memories(
        &mut self,
        batch: RecordBatch,
        schema: SchemaRef,
    ) -> UmbraResult<()> {
        self.append(super::MEMORIES_TABLE, batch, schema).await
    }
}
