use crate::planner::LogicalPlan;
use crate::storage::StorageEngine;
use std::sync::Arc;
use async_recursion::async_recursion;

#[async_recursion]
pub async fn execute(
    plan: LogicalPlan,
    storage_engine: &Arc<StorageEngine>,
) -> Result<ResultSet, String> {
    match plan {
        LogicalPlan::Projection { expr: _, input } => {
            // For simplicity, we'll just execute the input plan
            execute(*input, storage_engine).await
        }
        LogicalPlan::Selection { expr: _, input } => {
            // For simplicity, we'll just execute the input plan
            execute(*input, storage_engine).await
        }
        LogicalPlan::Scan { table_name, projection: _ } => {
            // Use the storage engine to scan the table
            scan_table(&table_name, storage_engine).await
        }
        LogicalPlan::CreateTable { table_name, columns } => {
            // Convert planner column definitions to storage column definitions
            let storage_columns = columns.into_iter().map(|col| {
                crate::storage::ColumnDef {
                    name: col.name,
                    data_type: match col.data_type {
                        crate::planner::DataType::Integer => crate::storage::DataType::Integer,
                        crate::planner::DataType::Text => crate::storage::DataType::Text,
                        crate::planner::DataType::Boolean => crate::storage::DataType::Boolean,
                        crate::planner::DataType::Float => crate::storage::DataType::Float,
                    },
                    nullable: col.nullable,
                }
            }).collect();
            
            storage_engine.create_table(table_name, storage_columns).await?;
            
            Ok(ResultSet {
                columns: vec!["result".to_string()],
                rows: vec![vec![Value::Text("Table created successfully".to_string())]],
            })
        }
        LogicalPlan::Insert { table_name, columns: _, values } => {
            // For simplicity, we only handle single row inserts
            if values.len() != 1 {
                return Err("Only single row inserts are supported".to_string());
            }
            
            let row_values = &values[0];
            let mut storage_values = Vec::new();
            
            // Convert planner values to storage values
            for expr in row_values {
                match expr {
                    crate::planner::Expr::Value(val) => {
                        let storage_val = match val {
                            crate::planner::Value::Integer(i) => crate::storage::Value::Integer(*i),
                            crate::planner::Value::Text(s) => crate::storage::Value::Text(s.clone()),
                            crate::planner::Value::Boolean(b) => crate::storage::Value::Boolean(*b),
                            crate::planner::Value::Null => crate::storage::Value::Null,
                        };
                        storage_values.push(storage_val);
                    }
                    _ => return Err("Only literal values are supported in INSERT".to_string()),
                }
            }
            
            storage_engine.insert_row(&table_name, storage_values).await?;
            
            Ok(ResultSet {
                columns: vec!["result".to_string()],
                rows: vec![vec![Value::Text("Row inserted successfully".to_string())]],
            })
        }
    }
}

async fn scan_table(
    table_name: &str,
    storage_engine: &Arc<StorageEngine>,
) -> Result<ResultSet, String> {
    // Get column names
    let columns = storage_engine.get_table_columns(table_name).await?;
    let column_names = columns.into_iter().map(|col| col.name).collect();
    
    // Scan the table from storage
    let mut scan = storage_engine.scan_table(table_name).await?;
    
    // Collect all rows
    let mut all_rows = Vec::new();
    while let Some(batch) = scan.next_batch(100).await {
        all_rows.extend(batch);
    }
    
    // Convert storage values to executor values
    let rows = all_rows.into_iter().map(|row| {
        row.into_iter().map(|val| val.into()).collect()
    }).collect();
    
    Ok(ResultSet {
        columns: column_names,
        rows,
    })
}

#[derive(Debug)]
pub struct ResultSet {
    pub columns: Vec<String>,
    pub rows: Vec<Vec<Value>>,
}

#[derive(Debug, Clone)]
pub enum Value {
    Integer(i64),
    Text(String),
    Boolean(bool),
    Float(f64),
    Null,
}

impl From<crate::storage::Value> for Value {
    fn from(storage_value: crate::storage::Value) -> Self {
        match storage_value {
            crate::storage::Value::Integer(i) => Value::Integer(i),
            crate::storage::Value::Text(s) => Value::Text(s),
            crate::storage::Value::Boolean(b) => Value::Boolean(b),
            crate::storage::Value::Float(f) => Value::Float(f),
            crate::storage::Value::Null => Value::Null,
        }
    }
}