mod parser;
mod analyzer;
mod planner;
mod executor;
mod storage;

use std::sync::Arc;
use storage::{StorageEngine, LocalFileSystemStore, ColumnDef, DataType, Value};

#[tokio::main]
async fn main() -> Result<(), String> {
    println!("Welcome to RDB - A Rust Database Implementation!");
    println!("===============================================");
    
    // Initialize the storage engine
    let base_path = "./data".to_string();
    let object_store = Arc::new(LocalFileSystemStore::new(base_path.clone()));
    let storage_engine = Arc::new(StorageEngine::new(object_store, base_path).await?);
    
    // Create some sample tables and insert data directly
    initialize_sample_data(&storage_engine).await?;
    
    // Flush the data to create segments
    storage_engine.flush().await?;
    
    // Example queries
    let queries = vec![
        "SELECT * FROM users",
        "SELECT * FROM products",
    ];
    
    for query in queries {
        execute_query(query, &storage_engine).await;
    }
    
    println!("Database execution completed.");
    Ok(())
}

async fn initialize_sample_data(storage_engine: &Arc<StorageEngine>) -> Result<(), String> {
    // Create users table
    let user_columns = vec![
        ColumnDef {
            name: "id".to_string(),
            data_type: DataType::Integer,
            nullable: false,
        },
        ColumnDef {
            name: "name".to_string(),
            data_type: DataType::Text,
            nullable: false,
        },
    ];
    
    storage_engine.create_table("users".to_string(), user_columns).await?;
    
    // Insert user data
    storage_engine.insert_row(
        "users",
        vec![
            Value::Integer(1),
            Value::Text("Alice".to_string()),
        ]
    ).await?;
    
    storage_engine.insert_row(
        "users",
        vec![
            Value::Integer(2),
            Value::Text("Bob".to_string()),
        ]
    ).await?;
    
    // Create products table
    let product_columns = vec![
        ColumnDef {
            name: "id".to_string(),
            data_type: DataType::Integer,
            nullable: false,
        },
        ColumnDef {
            name: "name".to_string(),
            data_type: DataType::Text,
            nullable: false,
        },
        ColumnDef {
            name: "price".to_string(),
            data_type: DataType::Float,
            nullable: false,
        },
    ];
    
    storage_engine.create_table("products".to_string(), product_columns).await?;
    
    // Insert product data
    storage_engine.insert_row(
        "products",
        vec![
            Value::Integer(1),
            Value::Text("Product A".to_string()),
            Value::Float(10.99),
        ]
    ).await?;
    
    storage_engine.insert_row(
        "products",
        vec![
            Value::Integer(2),
            Value::Text("Product B".to_string()),
            Value::Float(20.50),
        ]
    ).await?;
    
    Ok(())
}

async fn execute_query(query: &str, storage_engine: &Arc<StorageEngine>) {
    println!("Executing query: {}", query);
    
    // Parse the query
    match parser::parse(query) {
        Ok(statement) => {
            println!("✓ Parsed statement: {:?}", statement);
            
            // Analyze the statement
            match analyzer::analyze(statement) {
                Ok(analyzed) => {
                    println!("✓ Analyzed statement: {:?}", analyzed);
                    
                    // Plan the query
                    match planner::plan(analyzed) {
                        Ok(plan) => {
                            println!("✓ Logical plan: {:?}", plan);
                            
                            // Execute the plan with storage engine
                            match executor::execute(plan, storage_engine).await {
                                Ok(results) => {
                                    println!("✓ Query results:");
                                    println!("  Columns: {:?}", results.columns);
                                    for (i, row) in results.rows.iter().enumerate() {
                                        println!("  Row {}: {:?}", i + 1, row);
                                    }
                                }
                                Err(e) => println!("✗ Execution error: {}", e),
                            }
                        }
                        Err(e) => println!("✗ Planning error: {}", e),
                    }
                }
                Err(e) => println!("✗ Analysis error: {}", e),
            }
        }
        Err(e) => println!("✗ Parse error: {}", e),
    }
    
    println!(); // Empty line for readability
}