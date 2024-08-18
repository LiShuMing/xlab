#[derive(Debug, thiserror::Error)]
pub enum UmbraError {
    #[error("validation error: {0}")]
    Validation(String),
    #[error("not found: {0}")]
    NotFound(String),
    #[error("storage error: {0}")]
    Storage(String),
    #[error("embedding error: {0}")]
    Embedding(String),
    #[error("internal error: {0}")]
    Internal(String),
    #[error("iceberg error: {0}")]
    Iceberg(String),
}

pub type UmbraResult<T> = Result<T, UmbraError>;
