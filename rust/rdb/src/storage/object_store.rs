use async_trait::async_trait;
use bytes::Bytes;
use std::path::Path;

#[async_trait]
pub trait ObjectStore: Send + Sync {
    async fn put(&self, path: &str, data: Bytes) -> Result<(), String>;
    async fn get(&self, path: &str) -> Result<Bytes, String>;
    async fn delete(&self, path: &str) -> Result<(), String>;
    async fn list(&self, _prefix: &str) -> Result<Vec<String>, String> {
        // Default implementation
        Ok(Vec::new())
    }
    async fn fsync(&self, _path: &str) -> Result<(), String> {
        // Default implementation
        Ok(())
    }
    async fn atomic_rename(&self, from: &str, to: &str) -> Result<(), String>;
}

pub struct LocalFileSystemStore {
    pub base_path: String,
}

impl LocalFileSystemStore {
    pub fn new(base_path: String) -> Self {
        Self { base_path }
    }
}

#[async_trait]
impl ObjectStore for LocalFileSystemStore {
    async fn put(&self, path: &str, data: Bytes) -> Result<(), String> {
        let full_path = format!("{}/{}", self.base_path, path);
        let parent_dir = Path::new(&full_path).parent().unwrap();
        
        // Create directories if they don't exist
        tokio::fs::create_dir_all(parent_dir)
            .await
            .map_err(|e| format!("Failed to create directories: {}", e))?;
        
        tokio::fs::write(&full_path, data)
            .await
            .map_err(|e| format!("Failed to write file: {}", e))?;
        
        Ok(())
    }
    
    async fn get(&self, path: &str) -> Result<Bytes, String> {
        let full_path = format!("{}/{}", self.base_path, path);
        let data = tokio::fs::read(&full_path)
            .await
            .map_err(|e| format!("Failed to read file: {}", e))?;
        Ok(Bytes::from(data))
    }
    
    async fn delete(&self, path: &str) -> Result<(), String> {
        let full_path = format!("{}/{}", self.base_path, path);
        tokio::fs::remove_file(&full_path)
            .await
            .map_err(|e| format!("Failed to delete file: {}", e))?;
        Ok(())
    }
    
    async fn list(&self, _prefix: &str) -> Result<Vec<String>, String> {
        // Implementation will be added later
        Ok(Vec::new())
    }
    
    async fn fsync(&self, _path: &str) -> Result<(), String> {
        // On some systems, fsync might not be directly available in async context
        // This is a simplified implementation
        Ok(())
    }
    
    async fn atomic_rename(&self, from: &str, to: &str) -> Result<(), String> {
        let from_path = format!("{}/{}", self.base_path, from);
        let to_path = format!("{}/{}", self.base_path, to);
        
        tokio::fs::rename(&from_path, &to_path)
            .await
            .map_err(|e| format!("Failed to rename file: {}", e))?;
        
        Ok(())
    }
}