use sqlx::{Pool, Sqlite, Row};
use std::path::Path;
use crate::models::{Document, ReviewItem, Reflection, ReflectionStats};
use chrono::Utc;


#[derive(Clone)]
pub struct Database {
    pool: Pool<Sqlite>,
}

impl Database {
    pub async fn connect(db_path: &str) -> Result<Self, String> {
        let pool = sqlx::SqlitePool::connect(db_path)
            .await
            .map_err(|e| e.to_string())?;
        Ok(Self { pool })
    }

    pub async fn run_migrations(&self) -> Result<(), String> {
        sqlx::query("
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT,
                content TEXT,
                captured_at TEXT NOT NULL,
                clean_text_path TEXT,
                raw_html_path TEXT,
                status TEXT DEFAULT 'captured',
                topics TEXT,
                entities TEXT,
                word_count INTEGER DEFAULT 0
            )
        ").execute(&self.pool).await.map_err(|e| e.to_string())?;
        
        sqlx::query("
            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                mode TEXT NOT NULL,
                created_at TEXT NOT NULL,
                cost_ms INTEGER,
                result_json TEXT NOT NULL
            )
        ").execute(&self.pool).await.map_err(|e| e.to_string())?;
        
        sqlx::query("
            CREATE TABLE IF NOT EXISTS review_schedule (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                item_id TEXT NOT NULL,
                item_type TEXT NOT NULL,
                front TEXT NOT NULL,
                back TEXT NOT NULL,
                context TEXT,
                due_at TEXT NOT NULL,
                interval_days INTEGER DEFAULT 0,
                ease REAL DEFAULT 2.5,
                last_score INTEGER,
                streak INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        ").execute(&self.pool).await.map_err(|e| e.to_string())?;
        
        sqlx::query("
            CREATE TABLE IF NOT EXISTS reflections (
                id TEXT PRIMARY KEY,
                date TEXT NOT NULL UNIQUE,
                key_win TEXT,
                avoidance TEXT,
                next_fix TEXT,
                deep_work_min INTEGER DEFAULT 0,
                family_min INTEGER DEFAULT 0,
                sleep_h REAL DEFAULT 7.0,
                notes TEXT,
                created_at TEXT NOT NULL
            )
        ").execute(&self.pool).await.map_err(|e| e.to_string())?;
        
        // Create indexes
        sqlx::query("CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status)")
            .execute(&self.pool).await.map_err(|e| e.to_string())?;
        sqlx::query("CREATE INDEX IF NOT EXISTS idx_review_due_at ON review_schedule(due_at)")
            .execute(&self.pool).await.map_err(|e| e.to_string())?;
        sqlx::query("CREATE INDEX IF NOT EXISTS idx_reflections_date ON reflections(date)")
            .execute(&self.pool).await.map_err(|e| e.to_string())?;
        
        Ok(())
    }

    // Document operations
    pub async fn create_document(&self, doc: &Document) -> Result<(), String> {
        let topics_json = serde_json::to_string(&doc.topics).map_err(|e| e.to_string())?;
        let entities_json = serde_json::to_string(&doc.entities).map_err(|e| e.to_string())?;
        
        sqlx::query("
            INSERT INTO documents (id, type, title, url, content, captured_at, 
                clean_text_path, raw_html_path, status, topics, entities, word_count)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12)
        ")
        .bind(&doc.id)
        .bind(&doc.type_)
        .bind(&doc.title)
        .bind(&doc.url)
        .bind(&doc.content)
        .bind(&doc.captured_at)
        .bind(&doc.clean_text_path)
        .bind(&doc.raw_html_path)
        .bind(&doc.status)
        .bind(&topics_json)
        .bind(&entities_json)
        .bind(doc.word_count)
        .execute(&self.pool)
        .await
        .map_err(|e| e.to_string())?;
        
        Ok(())
    }

    pub async fn get_documents(&self, limit: i64, offset: i64) -> Result<Vec<Document>, String> {
        let rows = sqlx::query("
            SELECT id, type, title, url, content, captured_at, 
                clean_text_path, raw_html_path, status, topics, entities, word_count
            FROM documents
            ORDER BY captured_at DESC
            LIMIT ?1 OFFSET ?2
        ")
        .bind(limit)
        .bind(offset)
        .fetch_all(&self.pool)
        .await
        .map_err(|e| e.to_string())?;

        let mut documents = Vec::new();
        for row in rows {
            let topics_json: String = row.get("topics");
            let entities_json: String = row.get("entities");
            let topics: Vec<String> = serde_json::from_str(&topics_json).unwrap_or_default();
            let entities: Vec<String> = serde_json::from_str(&entities_json).unwrap_or_default();

            documents.push(Document {
                id: row.get("id"),
                type_: row.get("type"),
                title: row.get("title"),
                url: row.get("url"),
                content: row.get("content"),
                captured_at: row.get("captured_at"),
                clean_text_path: row.get("clean_text_path"),
                raw_html_path: row.get("raw_html_path"),
                status: row.get("status"),
                topics,
                entities,
                word_count: row.get("word_count"),
            });
        }
        Ok(documents)
    }

    pub async fn get_document(&self, id: &str) -> Result<Option<Document>, String> {
        let row = sqlx::query("
            SELECT id, type, title, url, content, captured_at, 
                clean_text_path, raw_html_path, status, topics, entities, word_count
            FROM documents WHERE id = ?1
        ")
        .bind(id)
        .fetch_optional(&self.pool)
        .await
        .map_err(|e| e.to_string())?;

        match row {
            Some(row) => {
                let topics_json: String = row.get("topics");
                let entities_json: String = row.get("entities");
                let topics: Vec<String> = serde_json::from_str(&topics_json).unwrap_or_default();
                let entities: Vec<String> = serde_json::from_str(&entities_json).unwrap_or_default();

                Ok(Some(Document {
                    id: row.get("id"),
                    type_: row.get("type"),
                    title: row.get("title"),
                    url: row.get("url"),
                    content: row.get("content"),
                    captured_at: row.get("captured_at"),
                    clean_text_path: row.get("clean_text_path"),
                    raw_html_path: row.get("raw_html_path"),
                    status: row.get("status"),
                    topics,
                    entities,
                    word_count: row.get("word_count"),
                }))
            }
            None => Ok(None),
        }
    }

    pub async fn delete_document(&self, id: &str) -> Result<bool, String> {
        let result = sqlx::query("DELETE FROM documents WHERE id = ?1")
            .bind(id)
            .execute(&self.pool)
            .await
            .map_err(|e| e.to_string())?;
        Ok(result.rows_affected() > 0)
    }

    pub async fn search_documents(&self, query: &str) -> Result<Vec<Document>, String> {
        let search_pattern = format!("%{}%", query);
        let rows = sqlx::query("
            SELECT id, type, title, url, content, captured_at, 
                clean_text_path, raw_html_path, status, topics, entities, word_count
            FROM documents
            WHERE title LIKE ?1 OR content LIKE ?1 OR url LIKE ?1
            ORDER BY captured_at DESC
        ")
        .bind(&search_pattern)
        .fetch_all(&self.pool)
        .await
        .map_err(|e| e.to_string())?;

        let mut documents = Vec::new();
        for row in rows {
            let topics_json: String = row.get("topics");
            let entities_json: String = row.get("entities");
            let topics: Vec<String> = serde_json::from_str(&topics_json).unwrap_or_default();
            let entities: Vec<String> = serde_json::from_str(&entities_json).unwrap_or_default();

            documents.push(Document {
                id: row.get("id"),
                type_: row.get("type"),
                title: row.get("title"),
                url: row.get("url"),
                content: row.get("content"),
                captured_at: row.get("captured_at"),
                clean_text_path: row.get("clean_text_path"),
                raw_html_path: row.get("raw_html_path"),
                status: row.get("status"),
                topics,
                entities,
                word_count: row.get("word_count"),
            });
        }
        Ok(documents)
    }

    pub async fn update_document_status(&self, id: &str, status: &str) -> Result<bool, String> {
        let result = sqlx::query("UPDATE documents SET status = ?1 WHERE id = ?2")
            .bind(status)
            .bind(id)
            .execute(&self.pool)
            .await
            .map_err(|e| e.to_string())?;
        Ok(result.rows_affected() > 0)
    }

    // Review operations
    pub async fn create_review_item(&self, item: &ReviewItem) -> Result<(), String> {
        sqlx::query("
            INSERT INTO review_schedule (id, type, item_id, item_type, front, back, context,
                due_at, interval_days, ease, last_score, streak, created_at)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13)
        ")
        .bind(&item.id)
        .bind(&item.type_)
        .bind(&item.item_id)
        .bind(&item.item_type)
        .bind(&item.front)
        .bind(&item.back)
        .bind(&item.context)
        .bind(&item.due_at)
        .bind(item.interval)
        .bind(item.ease)
        .bind(item.last_score)
        .bind(item.streak)
        .bind(&item.created_at)
        .execute(&self.pool)
        .await
        .map_err(|e| e.to_string())?;
        
        Ok(())
    }

    pub async fn get_review_queue(&self) -> Result<Vec<ReviewItem>, String> {
        let now = Utc::now().to_rfc3339();
        let rows = sqlx::query("
            SELECT id, type, item_id, item_type, front, back, context,
                due_at, interval_days, ease, last_score, streak, created_at
            FROM review_schedule
            WHERE due_at <= ?1
            ORDER BY due_at ASC
            LIMIT 50
        ")
        .bind(&now)
        .fetch_all(&self.pool)
        .await
        .map_err(|e| e.to_string())?;

        let mut items = Vec::new();
        for row in rows {
            items.push(ReviewItem {
                id: row.get("id"),
                type_: row.get("type"),
                item_id: row.get("item_id"),
                item_type: row.get("item_type"),
                front: row.get("front"),
                back: row.get("back"),
                context: row.get("context"),
                due_at: row.get("due_at"),
                interval: row.get("interval_days"),
                ease: row.get("ease"),
                last_score: row.get("last_score"),
                streak: row.get("streak"),
                created_at: row.get("created_at"),
            });
        }
        Ok(items)
    }

    pub async fn submit_review(&self, item_id: &str, score: i32) -> Result<(), String> {
        let item = self.get_review_item_by_item_id(item_id).await?;
        if item.is_none() {
            return Err("Review item not found".to_string());
        }
        let item = item.unwrap();

        // SM-2 algorithm
        let (new_interval, new_ease, new_streak) = calculate_srs(item.interval, item.ease, item.streak, score);
        let next_due = Utc::now() + chrono::Duration::days(new_interval);

        sqlx::query("
            UPDATE review_schedule
            SET interval_days = ?1, ease = ?2, last_score = ?3, streak = ?4, due_at = ?5
            WHERE item_id = ?6
        ")
        .bind(new_interval)
        .bind(new_ease)
        .bind(score)
        .bind(new_streak)
        .bind(next_due.to_rfc3339())
        .bind(item_id)
        .execute(&self.pool)
        .await
        .map_err(|e| e.to_string())?;

        Ok(())
    }

    async fn get_review_item_by_item_id(&self, item_id: &str) -> Result<Option<ReviewItem>, String> {
        let row = sqlx::query("
            SELECT id, type, item_id, item_type, front, back, context,
                due_at, interval_days, ease, last_score, streak, created_at
            FROM review_schedule WHERE item_id = ?1
        ")
        .bind(item_id)
        .fetch_optional(&self.pool)
        .await
        .map_err(|e| e.to_string())?;

        match row {
            Some(row) => Ok(Some(ReviewItem {
                id: row.get("id"),
                type_: row.get("type"),
                item_id: row.get("item_id"),
                item_type: row.get("item_type"),
                front: row.get("front"),
                back: row.get("back"),
                context: row.get("context"),
                due_at: row.get("due_at"),
                interval: row.get("interval_days"),
                ease: row.get("ease"),
                last_score: row.get("last_score"),
                streak: row.get("streak"),
                created_at: row.get("created_at"),
            })),
            None => Ok(None),
        }
    }

    // Reflection operations
    pub async fn save_reflection(&self, reflection: &Reflection) -> Result<(), String> {
        sqlx::query("
            INSERT OR REPLACE INTO reflections 
            (id, date, key_win, avoidance, next_fix, deep_work_min, family_min, sleep_h, notes, created_at)
            VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10)
        ")
        .bind(&reflection.id)
        .bind(&reflection.date)
        .bind(&reflection.key_win)
        .bind(&reflection.avoidance)
        .bind(&reflection.next_fix)
        .bind(reflection.deep_work_min)
        .bind(reflection.family_min)
        .bind(reflection.sleep_h)
        .bind(&reflection.notes)
        .bind(&reflection.created_at)
        .execute(&self.pool)
        .await
        .map_err(|e| e.to_string())?;
        
        Ok(())
    }

    pub async fn get_reflection(&self, date: &str) -> Result<Option<Reflection>, String> {
        let row = sqlx::query("
            SELECT id, date, key_win, avoidance, next_fix, deep_work_min, family_min, sleep_h, notes, created_at
            FROM reflections WHERE date = ?1
        ")
        .bind(date)
        .fetch_optional(&self.pool)
        .await
        .map_err(|e| e.to_string())?;

        match row {
            Some(row) => Ok(Some(Reflection {
                id: row.get("id"),
                date: row.get("date"),
                key_win: row.get("key_win"),
                avoidance: row.get("avoidance"),
                next_fix: row.get("next_fix"),
                deep_work_min: row.get("deep_work_min"),
                family_min: row.get("family_min"),
                sleep_h: row.get("sleep_h"),
                notes: row.get("notes"),
                created_at: row.get("created_at"),
            })),
            None => Ok(None),
        }
    }

    pub async fn get_reflection_log(&self, start_date: Option<&str>, end_date: Option<&str>) -> Result<Vec<Reflection>, String> {
        let mut query = String::from("
            SELECT id, date, key_win, avoidance, next_fix, deep_work_min, family_min, sleep_h, notes, created_at
            FROM reflections
        ");
        
        if start_date.is_some() || end_date.is_some() {
            query.push_str(" WHERE ");
            if let Some(start) = start_date {
                query.push_str(&format!("date >= '{}'", start));
                if end_date.is_some() {
                    query.push_str(" AND ");
                }
            }
            if let Some(end) = end_date {
                query.push_str(&format!("date <= '{}'", end));
            }
        }
        
        query.push_str(" ORDER BY date DESC");

        let rows = sqlx::query(&query)
            .fetch_all(&self.pool)
            .await
            .map_err(|e| e.to_string())?;

        let mut reflections = Vec::new();
        for row in rows {
            reflections.push(Reflection {
                id: row.get("id"),
                date: row.get("date"),
                key_win: row.get("key_win"),
                avoidance: row.get("avoidance"),
                next_fix: row.get("next_fix"),
                deep_work_min: row.get("deep_work_min"),
                family_min: row.get("family_min"),
                sleep_h: row.get("sleep_h"),
                notes: row.get("notes"),
                created_at: row.get("created_at"),
            });
        }
        Ok(reflections)
    }

    pub async fn get_reflection_stats(&self) -> Result<ReflectionStats, String> {
        let total: i64 = sqlx::query_scalar("SELECT COUNT(*) FROM reflections")
            .fetch_one(&self.pool)
            .await
            .map_err(|e| e.to_string())?;

        let avg_deep_work: Option<f64> = sqlx::query_scalar("SELECT AVG(deep_work_min) FROM reflections")
            .fetch_one(&self.pool)
            .await
            .map_err(|e| e.to_string())?;

        let avg_family: Option<f64> = sqlx::query_scalar("SELECT AVG(family_min) FROM reflections")
            .fetch_one(&self.pool)
            .await
            .map_err(|e| e.to_string())?;

        let avg_sleep: Option<f64> = sqlx::query_scalar("SELECT AVG(sleep_h) FROM reflections")
            .fetch_one(&self.pool)
            .await
            .map_err(|e| e.to_string())?;

        // Get recent wins
        let wins: Vec<String> = sqlx::query_scalar("SELECT key_win FROM reflections WHERE key_win IS NOT NULL ORDER BY date DESC LIMIT 5")
            .fetch_all(&self.pool)
            .await
            .map_err(|e| e.to_string())?;

        // Get common avoidances
        let avoidances: Vec<String> = sqlx::query_scalar("SELECT avoidance FROM reflections WHERE avoidance IS NOT NULL ORDER BY date DESC LIMIT 5")
            .fetch_all(&self.pool)
            .await
            .map_err(|e| e.to_string())?;

        // Calculate current streak
        let streak = self.calculate_streak().await?;

        Ok(ReflectionStats {
            total_reflections: total as i32,
            avg_deep_work_min: avg_deep_work.unwrap_or(0.0),
            avg_family_min: avg_family.unwrap_or(0.0),
            avg_sleep_h: avg_sleep.unwrap_or(7.0),
            current_streak: streak,
            recent_wins: wins,
            common_avoidance: avoidances,
        })
    }

    async fn calculate_streak(&self) -> Result<i32, String> {
        let dates: Vec<String> = sqlx::query_scalar("SELECT date FROM reflections ORDER BY date DESC")
            .fetch_all(&self.pool)
            .await
            .map_err(|e| e.to_string())?;

        if dates.is_empty() {
            return Ok(0);
        }

        let today = Utc::now().date_naive();
        let mut streak = 0;
        let mut check_date = today;

        for date_str in dates {
            if let Ok(date) = chrono::NaiveDate::parse_from_str(&date_str, "%Y-%m-%d") {
                if date == check_date {
                    streak += 1;
                    check_date = check_date.pred_opt().unwrap_or(check_date);
                } else if date == check_date.pred_opt().unwrap_or(check_date) {
                    // Continue streak
                    streak += 1;
                    check_date = date.pred_opt().unwrap_or(date);
                } else {
                    break;
                }
            }
        }

        Ok(streak)
    }

    pub async fn has_analysis(&self, document_id: &str) -> Result<bool, String> {
        let count: i64 = sqlx::query_scalar("SELECT COUNT(*) FROM analyses WHERE document_id = ?1")
            .bind(document_id)
            .fetch_one(&self.pool)
            .await
            .map_err(|e| e.to_string())?;
        Ok(count > 0)
    }
}

pub async fn run_migrations(db_path: &str) -> Result<(), String> {
    if let Some(parent) = Path::new(db_path).parent() {
        std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    
    let db = Database::connect(db_path).await?;
    db.run_migrations().await
}

// SM-2 SRS algorithm
fn calculate_srs(_interval: i64, ease: f64, streak: i32, score: i32) -> (i64, f64, i32) {
    let intervals = [1, 3, 7, 14, 30, 60, 120, 240];
    
    if score < 3 {
        // Reset
        return (1, ease.max(1.3), 0);
    }

    let new_streak = streak + 1;
    let idx = (new_streak as usize).min(intervals.len() - 1);
    let new_interval = intervals[idx];
    
    // Adjust ease factor
    let new_ease = (ease + 0.1 - (5 - score) as f64 * (0.08 + (5 - score) as f64 * 0.02)).max(1.3);
    
    (new_interval, new_ease, new_streak)
}
