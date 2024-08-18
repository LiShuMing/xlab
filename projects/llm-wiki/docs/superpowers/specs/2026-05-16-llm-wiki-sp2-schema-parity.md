# SP2 — Schema 真实化（Postgres + File）

- **状态**: Draft → 实现中
- **创建**: 2026-05-16
- **关联**: RFC-001-v2 §10, SP1

## 目标

将 Postgres schema 从 JSONB-POC 升级为 RFC §10 完整版，同时补齐 Go domain 类型与 file 后端实现。

## 当前状态 vs 目标

| RFC 表 | POC 表 | POC 问题 | 目标 |
|--------|--------|----------|------|
| 10.1 app_user | llm_wiki_app_user | doc JSONB 存所有字段 | 保持 doc（不改，破坏面大），只加 extraction_job 引用 |
| 10.2 source_asset | llm_wiki_source_asset | 同上 | 保持 doc |
| 10.3 extraction_job | — | **不存在** | 新增 |
| 10.4 context_item | llm_wiki_context_item | doc JSONB | 保持 doc |
| 10.5 context_vector | llm_wiki_context_vector | doc JSONB | 保持 doc |
| 10.6 entity | — | **不存在** | 新增 |
| 10.7 user_entity_edge | — | **不存在** | 新增 |
| 10.8 user_context_summary | — | **不存在** | 新增 |
| 10.9 model_call_log | llm_wiki_model_call_log | doc JSONB | 只补 RFC 列（image_count/cost） |
| 10.10 usage_audit | llm_wiki_context_usage_audit | doc JSONB | 保持 doc |
| 10.11 match_result | llm_wiki_match_result | doc JSONB | 补 score_breakdown/context_ids/safe_context_pack/bridge_result/privacy_check 列 |

**策略**：不迁移现有 POC 表的 doc→typed columns（风险太大，已有数据兼容无保证）。只新增缺失表 + 给 match_result/model_call_log 补列。现有 doc 列继续承载主要数据。

## 新增 Go domain 类型

```go
// Entity — RFC §10.6
type Entity struct {
    ID            string         `json:"id"`
    EntityType    string         `json:"entity_type"`
    Name          string         `json:"name"`
    CanonicalName string         `json:"canonical_name,omitempty"`
    Attrs         map[string]any `json:"attrs"`
    CreatedAt     time.Time      `json:"created_at"`
}

// UserEntityEdge — RFC §10.7
type UserEntityEdge struct {
    UserID           string     `json:"user_id"`
    EntityID         string     `json:"entity_id"`
    Weight           float64    `json:"weight"`
    Confidence       float64    `json:"confidence"`
    SourceContextID  string     `json:"source_context_id,omitempty"`
    Visibility       Visibility `json:"visibility"`
    Sensitivity      Sensitivity `json:"sensitivity"`
    UpdatedAt        time.Time  `json:"updated_at"`
}

// UserContextSummary — RFC §10.8
type UserContextSummary struct {
    ID                string         `json:"id"`
    UserID            string         `json:"user_id"`
    SummaryType       string         `json:"summary_type"`
    Text              string         `json:"text"`
    Attrs             map[string]any `json:"attrs"`
    SourceContextIDs  []string       `json:"source_context_ids"`
    Confidence        float64        `json:"confidence"`
    Sensitivity       Sensitivity    `json:"sensitivity"`
    Visibility        Visibility     `json:"visibility"`
    Purpose           []Purpose      `json:"purpose"`
    Version           int            `json:"version"`
    CreatedAt         time.Time      `json:"created_at"`
    UpdatedAt         time.Time      `json:"updated_at"`
}

// ExtractionJob — RFC §10.3
type ExtractionJob struct {
    ID              string         `json:"id"`
    UserID          string         `json:"user_id"`
    SourceAssetID   string         `json:"source_asset_id,omitempty"`
    JobType         string         `json:"job_type"`
    Status          string         `json:"status"`
    Input           map[string]any `json:"input"`
    Output          map[string]any `json:"output"`
    Error           string         `json:"error,omitempty"`
    ModelProvider   string         `json:"model_provider,omitempty"`
    ModelName       string         `json:"model_name,omitempty"`
    PromptVersion   string         `json:"prompt_version,omitempty"`
    StartedAt       *time.Time     `json:"started_at,omitempty"`
    FinishedAt      *time.Time     `json:"finished_at,omitempty"`
    CreatedAt       time.Time      `json:"created_at"`
}
```

## Repository 接口扩展

新增方法：

```go
// Entity
AddEntity(entity Entity) error
EntityByID(id string) (*Entity, error)
EntityByName(name string) (*Entity, error)

// UserEntityEdge
UpsertUserEntityEdge(edge UserEntityEdge) error
UserEntityEdges(userID string) ([]UserEntityEdge, error)

// UserContextSummary
AddUserContextSummary(summary UserContextSummary) error
UserContextSummaries(userID string) ([]UserContextSummary, error)

// ExtractionJob
AddExtractionJob(job ExtractionJob) error
UpdateExtractionJob(id string, update func(*ExtractionJob) error) (*ExtractionJob, error)
ExtractionJobsByUser(userID string) ([]ExtractionJob, error)
```

## 成功标准

1. `go build ./... && go test ./...` 通过
2. Postgres schema 包含全部 11 张表
3. File 后端 JSON 包含新类型数据并可读写
4. 新增 5 个 Postgres 集成测试用例
5. 现有 `ctx demo run` 无回归
