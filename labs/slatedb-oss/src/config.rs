use std::fmt;
use std::path::{Path, PathBuf};

use anyhow::{anyhow, Context, Result};

/// Default dedicated OSS bucket created without versioning for SlateDB CAS semantics.
pub const DEFAULT_OSS_BUCKET: &str = "xlab-slatedb-dev";

/// Connection settings for Alibaba Cloud OSS.
///
/// Credentials are intentionally redacted in [`fmt::Debug`] so they cannot leak
/// into test logs or error traces.
#[derive(Clone)]
pub struct OssConfig {
    pub endpoint: String,
    pub bucket: String,
    pub root: String,
    pub access_key_id: String,
    pub access_key_secret: String,
}

impl fmt::Debug for OssConfig {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("OssConfig")
            .field("endpoint", &self.endpoint)
            .field("bucket", &self.bucket)
            .field("root", &self.root)
            .field("access_key_id", &"<REDACTED>")
            .field("access_key_secret", &"<REDACTED>")
            .finish()
    }
}

impl OssConfig {
    /// Load OSS settings from environment variables, falling back to an optional
    /// dotenv file (defaulting to `$HOME/.env` when present).
    ///
    /// Precedence for each setting:
    /// 1. Explicit CLI override (`bucket_override`, `root_override`, `endpoint_override`)
    /// 2. `SLATEDB_OSS_*` environment variable
    /// 3. `DB_RADAR_OSS_*` fallback (only for endpoint and credentials; never
    ///    silently targets `dbradar-dev` because that bucket has versioning enabled)
    pub fn load(
        env_file: Option<&Path>,
        bucket_override: Option<&str>,
        root_override: Option<&str>,
        endpoint_override: Option<&str>,
    ) -> Result<Self> {
        load_dotenv_if_present(env_file)?;

        let access_key_id = first_non_empty_env(&[
            "SLATEDB_OSS_ACCESS_KEY_ID",
            "DB_RADAR_OSS_ACCESS_KEY_ID",
            "OSS_ACCESS_KEY_ID",
        ])
        .ok_or_else(|| {
            anyhow!(
                "missing OSS access key id (set SLATEDB_OSS_ACCESS_KEY_ID or DB_RADAR_OSS_ACCESS_KEY_ID)"
            )
        })?;

        let access_key_secret = first_non_empty_env(&[
            "SLATEDB_OSS_ACCESS_KEY_SECRET",
            "DB_RADAR_OSS_ACCESS_KEY_SECRET",
            "OSS_ACCESS_KEY_SECRET",
        ])
        .ok_or_else(|| {
            anyhow!(
                "missing OSS access key secret (set SLATEDB_OSS_ACCESS_KEY_SECRET or DB_RADAR_OSS_ACCESS_KEY_SECRET)"
            )
        })?;

        let raw_endpoint = endpoint_override
            .map(str::to_string)
            .or_else(|| {
                first_non_empty_env(&[
                    "SLATEDB_OSS_ENDPOINT",
                    "DB_RADAR_OSS_ENDPOINT",
                    "OSS_ENDPOINT",
                ])
            })
            .ok_or_else(|| {
                anyhow!("missing OSS endpoint (set SLATEDB_OSS_ENDPOINT or DB_RADAR_OSS_ENDPOINT)")
            })?;

        let bucket = bucket_override
            .map(str::to_string)
            .or_else(|| first_non_empty_env(&["SLATEDB_OSS_BUCKET"]))
            .unwrap_or_else(|| DEFAULT_OSS_BUCKET.to_string());

        let root = root_override
            .map(str::to_string)
            .or_else(|| first_non_empty_env(&["SLATEDB_OSS_ROOT"]))
            .unwrap_or_else(|| "/".to_string());

        Ok(Self {
            endpoint: normalize_endpoint(&raw_endpoint),
            bucket: bucket.trim().to_string(),
            root: normalize_root(&root),
            access_key_id,
            access_key_secret,
        })
    }
}

fn load_dotenv_if_present(explicit_path: Option<&Path>) -> Result<()> {
    if let Some(path) = explicit_path {
        dotenvy::from_path(path)
            .with_context(|| format!("failed to load env file {}", path.display()))?;
        return Ok(());
    }
    if let Ok(home) = std::env::var("HOME") {
        let default_env = PathBuf::from(home).join(".env");
        if default_env.is_file() {
            // Best-effort: existing process env vars always take precedence in dotenvy.
            let _ = dotenvy::from_path(&default_env);
        }
    }
    Ok(())
}

fn first_non_empty_env(keys: &[&str]) -> Option<String> {
    keys.iter().find_map(|key| {
        std::env::var(key)
            .ok()
            .map(|val| val.trim().to_string())
            .filter(|val| !val.is_empty())
    })
}

pub fn normalize_endpoint(raw: &str) -> String {
    let trimmed = raw.trim().trim_end_matches('/');
    if trimmed.starts_with("https://") || trimmed.starts_with("http://") {
        trimmed.to_string()
    } else {
        format!("https://{trimmed}")
    }
}

pub fn normalize_root(raw: &str) -> String {
    let trimmed = raw.trim().trim_matches('/');
    if trimmed.is_empty() {
        "/".to_string()
    } else {
        format!("/{trimmed}")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn normalizes_endpoint_scheme() {
        assert_eq!(
            normalize_endpoint("oss-cn-beijing.aliyuncs.com/"),
            "https://oss-cn-beijing.aliyuncs.com"
        );
        assert_eq!(
            normalize_endpoint("https://oss-cn-beijing.aliyuncs.com"),
            "https://oss-cn-beijing.aliyuncs.com"
        );
        assert_eq!(
            normalize_endpoint("http://127.0.0.1:9000/"),
            "http://127.0.0.1:9000"
        );
    }

    #[test]
    fn normalizes_root_prefix() {
        assert_eq!(normalize_root(""), "/");
        assert_eq!(normalize_root("/"), "/");
        assert_eq!(normalize_root("e2e/run1/"), "/e2e/run1");
    }

    #[test]
    fn debug_redacts_secrets() {
        let cfg = OssConfig {
            endpoint: "https://oss-cn-beijing.aliyuncs.com".to_string(),
            bucket: "xlab-slatedb-dev".to_string(),
            root: "/e2e".to_string(),
            access_key_id: "DUMMY_KEY_ID_SHOULD_NOT_SHOW".to_string(),
            access_key_secret: "DUMMY_SECRET_SHOULD_NOT_SHOW".to_string(),
        };
        let rendered = format!("{cfg:?}");
        assert!(!rendered.contains("DUMMY_KEY_ID"));
        assert!(!rendered.contains("DUMMY_SECRET"));
        assert!(rendered.contains("xlab-slatedb-dev"));
    }
}
