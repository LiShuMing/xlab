pub mod vector;
pub mod fulltext;
pub mod entity;

/// Index configuration.
#[derive(Debug, Clone)]
pub struct IndexConfig {
    pub vector: VectorIndexConfig,
    pub fulltext: FulltextConfig,
    pub entity: EntityIndexConfig,
}

#[derive(Debug, Clone)]
pub struct VectorIndexConfig {
    pub num_partitions: usize,
    pub num_sub_vectors: usize,
    pub distance: String,
}

#[derive(Debug, Clone)]
pub struct FulltextConfig {
    pub enabled: bool,
    pub column: String,
}

#[derive(Debug, Clone)]
pub struct EntityIndexConfig {
    /// Entity boost weight in fusion: default 0.2
    pub weight: f64,
}

impl Default for IndexConfig {
    fn default() -> Self {
        Self {
            vector: VectorIndexConfig {
                num_partitions: 100,
                num_sub_vectors: 96,
                distance: "cosine".to_string(),
            },
            fulltext: FulltextConfig {
                enabled: true,
                column: "text_lemma".to_string(),
            },
            entity: EntityIndexConfig { weight: 0.2 },
        }
    }
}
