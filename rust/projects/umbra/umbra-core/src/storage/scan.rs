use arrow_array::RecordBatch;
use futures::TryStreamExt;
use lance::dataset::scanner::Scanner;

use crate::{UmbraError, UmbraResult};
use super::StorageLayer;

impl StorageLayer {
    /// Create a scanner for the given table with optional column projection.
    pub fn scan(
        &self,
        table_name: &str,
        columns: Option<&[&str]>,
    ) -> UmbraResult<Scanner> {
        let ds = self
            .get(table_name)
            .ok_or_else(|| UmbraError::NotFound(format!("table {table_name} not found")))?;

        let mut scanner = ds.scan();
        if let Some(cols) = columns {
            scanner.project(cols).map_err(|e| {
                UmbraError::Storage(format!("project columns: {e}"))
            })?;
        }
        Ok(scanner)
    }

    /// Scan and collect all record batches into a vector.
    pub async fn scan_all(
        &self,
        table_name: &str,
        columns: Option<&[&str]>,
    ) -> UmbraResult<Vec<RecordBatch>> {
        let scanner = self.scan(table_name, columns)?;
        let stream = scanner.try_into_stream().await.map_err(|e| {
            UmbraError::Storage(format!("scan {table_name}: {e}"))
        })?;
        stream
            .try_collect::<Vec<_>>()
            .await
            .map_err(|e| UmbraError::Storage(format!("collect {table_name}: {e}")))
    }
}
