# SP2 — Schema 真实化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐 RFC §10 缺失表 (extraction_job, entity, user_entity_edge, user_context_summary) + 补 match_result/model_call_log 缺失列 + Go domain 类型 + repo 接口扩展。

**Architecture:** 新增 domain 类型→扩展 Repository 接口→Postgres 端新 DDL→file 端 JSON 存储→repo 方法实现→集成测试。

**Tech Stack:** Go 1.25, pgx/v5, RFC §10 DDL。

---

### Task 1: 新增 Go domain 类型

**Files:**
- Create: `internal/domain/entity_types.go`

- [ ] **Step 1: 创建 entity_types.go**

```go
package domain

import "time"

type Entity struct {
	ID            string         `json:"id"`
	EntityType    string         `json:"entity_type"`    // interest, place, activity, topic, object
	Name          string         `json:"name"`
	CanonicalName string         `json:"canonical_name,omitempty"`
	Attrs         map[string]any `json:"attrs"`
	CreatedAt     time.Time      `json:"created_at"`
}

type UserEntityEdge struct {
	UserID          string      `json:"user_id"`
	EntityID        string      `json:"entity_id"`
	Weight          float64     `json:"weight"`
	Confidence      float64     `json:"confidence"`
	SourceContextID string      `json:"source_context_id,omitempty"`
	Visibility      Visibility  `json:"visibility"`
	Sensitivity     Sensitivity `json:"sensitivity"`
	UpdatedAt       time.Time   `json:"updated_at"`
}

type UserContextSummary struct {
	ID               string         `json:"id"`
	UserID           string         `json:"user_id"`
	SummaryType      string         `json:"summary_type"` // stable, recent, social_card, intent, travel, food, work
	Text             string         `json:"text"`
	Attrs            map[string]any `json:"attrs"`
	SourceContextIDs []string       `json:"source_context_ids"`
	Confidence       float64        `json:"confidence"`
	Sensitivity      Sensitivity    `json:"sensitivity"`
	Visibility       Visibility     `json:"visibility"`
	Purpose          []Purpose      `json:"purpose"`
	Version          int            `json:"version"`
	CreatedAt        time.Time      `json:"created_at"`
	UpdatedAt        time.Time      `json:"updated_at"`
}

type ExtractionJob struct {
	ID            string         `json:"id"`
	UserID        string         `json:"user_id"`
	SourceAssetID string         `json:"source_asset_id,omitempty"`
	JobType       string         `json:"job_type"` // exif, vision, embedding, summary
	Status        string         `json:"status"`    // pending, running, succeeded, failed
	Input         map[string]any `json:"input"`
	Output        map[string]any `json:"output"`
	Error         string         `json:"error,omitempty"`
	ModelProvider string         `json:"model_provider,omitempty"`
	ModelName     string         `json:"model_name,omitempty"`
	PromptVersion string         `json:"prompt_version,omitempty"`
	StartedAt     *time.Time     `json:"started_at,omitempty"`
	FinishedAt    *time.Time     `json:"finished_at,omitempty"`
	CreatedAt     time.Time      `json:"created_at"`
}
```

- [ ] **Step 2: 验证编译**

```bash
go build ./...
```

- [ ] **Step 3: Commit**

```bash
git add internal/domain/entity_types.go
git commit -m "feat(domain): add Entity, UserEntityEdge, UserContextSummary, ExtractionJob types"
```

---

### Task 2: 扩展 Repository 接口

**Files:**
- Modify: `internal/repository/store.go` (add interface methods)

- [ ] **Step 1: 在 Repository interface 末尾追加新方法**

```go
// Entity
AddEntity(entity domain.Entity) error
EntityByID(id string) (*domain.Entity, error)
EntityByName(name string) (*domain.Entity, error)

// UserEntityEdge
UpsertUserEntityEdge(edge domain.UserEntityEdge) error
UserEntityEdges(userID string) ([]domain.UserEntityEdge, error)

// UserContextSummary
AddUserContextSummary(summary domain.UserContextSummary) error
UserContextSummaries(userID string) ([]domain.UserContextSummary, error)

// ExtractionJob
AddExtractionJob(job domain.ExtractionJob) error
UpdateExtractionJob(id string, update func(*domain.ExtractionJob) error) (*domain.ExtractionJob, error)
ExtractionJobsByUser(userID string) ([]domain.ExtractionJob, error)
```

- [ ] **Step 2: 验证编译 — 应该失败（编译错误）**

```bash
go build ./... 2>&1 | head -20
```

Expected: 编译错误 — file store 和 postgres store 没有实现新接口方法。

- [ ] **Step 3: Commit**

```bash
git add internal/repository/store.go
git commit -m "feat(repo): add Entity/Edge/Summary/Job methods to Repository interface"
```

---

### Task 3: File 后端实现新接口方法

**Files:**
- Create: `internal/repository/entity_store.go` (file 后端对 entity/edge/summary/job 的实现)

- [ ] **Step 1: 扩展 State struct**

在 `store.go` 的 `State struct` 中添加：

```go
Entities  []domain.Entity              `json:"entities"`
Edges     []domain.UserEntityEdge      `json:"edges"`
Summaries []domain.UserContextSummary  `json:"summaries"`
Jobs      []domain.ExtractionJob       `json:"jobs"`
```

- [ ] **Step 2: 创建 entity_store.go**

```go
package repository

import (
	"fmt"
	"time"

	"github.com/LiShuMing/xlab/liminalis/llm-wiki/internal/domain"
)

// ── Entity ──

func (s *Store) AddEntity(entity domain.Entity) error {
	if entity.ID == "" {
		entity.ID = domain.NewID("ent")
	}
	if entity.CreatedAt.IsZero() {
		entity.CreatedAt = time.Now()
	}
	s.State.Entities = append(s.State.Entities, entity)
	return s.Save()
}

func (s *Store) EntityByID(id string) (*domain.Entity, error) {
	for i := range s.State.Entities {
		if s.State.Entities[i].ID == id {
			return &s.State.Entities[i], nil
		}
	}
	return nil, fmt.Errorf("entity %q not found", id)
}

func (s *Store) EntityByName(name string) (*domain.Entity, error) {
	for i := range s.State.Entities {
		if s.State.Entities[i].Name == name || s.State.Entities[i].CanonicalName == name {
			return &s.State.Entities[i], nil
		}
	}
	return nil, fmt.Errorf("entity name %q not found", name)
}

// ── UserEntityEdge ──

func (s *Store) UpsertUserEntityEdge(edge domain.UserEntityEdge) error {
	edge.UpdatedAt = time.Now()
	for i := range s.State.Edges {
		if s.State.Edges[i].UserID == edge.UserID && s.State.Edges[i].EntityID == edge.EntityID {
			s.State.Edges[i] = edge
			return s.Save()
		}
	}
	s.State.Edges = append(s.State.Edges, edge)
	return s.Save()
}

func (s *Store) UserEntityEdges(userID string) ([]domain.UserEntityEdge, error) {
	var out []domain.UserEntityEdge
	for _, e := range s.State.Edges {
		if e.UserID == userID {
			out = append(out, e)
		}
	}
	return out, nil
}

// ── UserContextSummary ──

func (s *Store) AddUserContextSummary(summary domain.UserContextSummary) error {
	if summary.ID == "" {
		summary.ID = domain.NewID("sum")
	}
	if summary.CreatedAt.IsZero() {
		summary.CreatedAt = time.Now()
	}
	if summary.UpdatedAt.IsZero() {
		summary.UpdatedAt = time.Now()
	}
	s.State.Summaries = append(s.State.Summaries, summary)
	return s.Save()
}

func (s *Store) UserContextSummaries(userID string) ([]domain.UserContextSummary, error) {
	var out []domain.UserContextSummary
	for _, s := range s.State.Summaries {
		if s.UserID == userID {
			out = append(out, s)
		}
	}
	return out, nil
}

// ── ExtractionJob ──

func (s *Store) AddExtractionJob(job domain.ExtractionJob) error {
	if job.ID == "" {
		job.ID = domain.NewID("job")
	}
	if job.CreatedAt.IsZero() {
		job.CreatedAt = time.Now()
	}
	s.State.Jobs = append(s.State.Jobs, job)
	return s.Save()
}

func (s *Store) UpdateExtractionJob(id string, update func(*domain.ExtractionJob) error) (*domain.ExtractionJob, error) {
	for i := range s.State.Jobs {
		if s.State.Jobs[i].ID == id {
			if update != nil {
				if err := update(&s.State.Jobs[i]); err != nil {
					return nil, err
				}
			}
			if err := s.Save(); err != nil {
				return nil, err
			}
			j := s.State.Jobs[i]
			return &j, nil
		}
	}
	return nil, fmt.Errorf("extraction job %q not found", id)
}

func (s *Store) ExtractionJobsByUser(userID string) ([]domain.ExtractionJob, error) {
	var out []domain.ExtractionJob
	for _, j := range s.State.Jobs {
		if j.UserID == userID {
			out = append(out, j)
		}
	}
	return out, nil
}
```

- [ ] **Step 3: 验证编译**

```bash
go build ./...
```

Expected: 编译通过（file store 满足了接口）。

- [ ] **Step 4: Commit**

```bash
git add internal/repository/store.go internal/repository/entity_store.go
git commit -m "feat(repo): implement Entity/Edge/Summary/Job for file backend"
```

---

### Task 4: Postgres 后端新表 DDL

**Files:**
- Modify: `internal/repository/postgres.go` (追加 DDL)

- [ ] **Step 1: 在 postgresSchema 常量末尾追加 CREATE TABLE**

在 `postgresSchema` 的结束 backtick 之前（`idx_llm_wiki_match_user` 行之后）追加：

```sql

CREATE TABLE IF NOT EXISTS llm_wiki_entity (
  id TEXT PRIMARY KEY,
  entity_type TEXT NOT NULL,
  name TEXT NOT NULL,
  canonical_name TEXT,
  attrs JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_llm_wiki_entity_type ON llm_wiki_entity(entity_type);
CREATE INDEX IF NOT EXISTS idx_llm_wiki_entity_name ON llm_wiki_entity(name);

CREATE TABLE IF NOT EXISTS llm_wiki_user_entity_edge (
  user_id TEXT NOT NULL REFERENCES llm_wiki_app_user(id),
  entity_id TEXT NOT NULL REFERENCES llm_wiki_entity(id),
  weight NUMERIC(5,3) NOT NULL,
  confidence NUMERIC(4,3) DEFAULT 0,
  source_context_id TEXT REFERENCES llm_wiki_context_item(id),
  visibility TEXT NOT NULL,
  sensitivity SMALLINT NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, entity_id)
);
CREATE INDEX IF NOT EXISTS idx_llm_wiki_edge_user ON llm_wiki_user_entity_edge(user_id);

CREATE TABLE IF NOT EXISTS llm_wiki_user_context_summary (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES llm_wiki_app_user(id),
  summary_type TEXT NOT NULL,
  text TEXT NOT NULL,
  attrs JSONB NOT NULL DEFAULT '{}',
  source_context_ids TEXT[] DEFAULT '{}',
  confidence NUMERIC(4,3),
  sensitivity SMALLINT NOT NULL,
  visibility TEXT NOT NULL,
  purpose TEXT[] NOT NULL DEFAULT '{}',
  version INT NOT NULL DEFAULT 1,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_llm_wiki_summary_user ON llm_wiki_user_context_summary(user_id);

CREATE TABLE IF NOT EXISTS llm_wiki_extraction_job (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES llm_wiki_app_user(id),
  source_asset_id TEXT REFERENCES llm_wiki_source_asset(id),
  job_type TEXT NOT NULL,
  status TEXT NOT NULL,
  input JSONB NOT NULL DEFAULT '{}',
  output JSONB NOT NULL DEFAULT '{}',
  error TEXT,
  model_provider TEXT,
  model_name TEXT,
  prompt_version TEXT,
  started_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_llm_wiki_job_user ON llm_wiki_extraction_job(user_id, status);
```

- [ ] **Step 2: 验证编译**

```bash
go build ./...
```

- [ ] **Step 3: Commit**

```bash
git add internal/repository/postgres.go
git commit -m "feat(repo): add Entity/Edge/Summary/Job DDL to postgres schema"
```

---

### Task 5: Postgres 后端实现新接口方法

**Files:**
- Create: `internal/repository/entity_postgres.go`

- [ ] **Step 1: 创建 entity_postgres.go**

```go
package repository

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/LiShuMing/xlab/liminalis/llm-wiki/internal/domain"
)

// ── Entity ──

func (s *PostgresStore) AddEntity(entity domain.Entity) error {
	if entity.ID == "" {
		entity.ID = domain.NewID("ent")
	}
	if entity.CreatedAt.IsZero() {
		entity.CreatedAt = time.Now()
	}
	attrs, _ := json.Marshal(entity.Attrs)
	_, err := s.pool.Exec(context.Background(),
		`INSERT INTO llm_wiki_entity (id, entity_type, name, canonical_name, attrs, created_at)
		 VALUES ($1, $2, $3, $4, $5, $6)`,
		entity.ID, entity.EntityType, entity.Name, entity.CanonicalName, attrs, entity.CreatedAt)
	if err != nil {
		return fmt.Errorf("add entity: %w", err)
	}
	return nil
}

func (s *PostgresStore) EntityByID(id string) (*domain.Entity, error) {
	var e domain.Entity
	var attrs []byte
	err := s.pool.QueryRow(context.Background(),
		`SELECT id, entity_type, name, canonical_name, attrs, created_at
		 FROM llm_wiki_entity WHERE id = $1`, id).
		Scan(&e.ID, &e.EntityType, &e.Name, &e.CanonicalName, &attrs, &e.CreatedAt)
	if err != nil {
		return nil, fmt.Errorf("entity by id: %w", err)
	}
	json.Unmarshal(attrs, &e.Attrs)
	return &e, nil
}

func (s *PostgresStore) EntityByName(name string) (*domain.Entity, error) {
	var e domain.Entity
	var attrs []byte
	err := s.pool.QueryRow(context.Background(),
		`SELECT id, entity_type, name, canonical_name, attrs, created_at
		 FROM llm_wiki_entity WHERE name = $1 OR canonical_name = $1 LIMIT 1`, name).
		Scan(&e.ID, &e.EntityType, &e.Name, &e.CanonicalName, &attrs, &e.CreatedAt)
	if err != nil {
		return nil, fmt.Errorf("entity by name %q: %w", name, err)
	}
	json.Unmarshal(attrs, &e.Attrs)
	return &e, nil
}

// ── UserEntityEdge ──

func (s *PostgresStore) UpsertUserEntityEdge(edge domain.UserEntityEdge) error {
	edge.UpdatedAt = time.Now()
	_, err := s.pool.Exec(context.Background(),
		`INSERT INTO llm_wiki_user_entity_edge
		 (user_id, entity_id, weight, confidence, source_context_id, visibility, sensitivity, updated_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
		 ON CONFLICT (user_id, entity_id) DO UPDATE SET
		   weight = EXCLUDED.weight,
		   confidence = EXCLUDED.confidence,
		   source_context_id = EXCLUDED.source_context_id,
		   visibility = EXCLUDED.visibility,
		   sensitivity = EXCLUDED.sensitivity,
		   updated_at = EXCLUDED.updated_at`,
		edge.UserID, edge.EntityID, edge.Weight, edge.Confidence,
		edge.SourceContextID, edge.Visibility, edge.Sensitivity, edge.UpdatedAt)
	if err != nil {
		return fmt.Errorf("upsert entity edge: %w", err)
	}
	return nil
}

func (s *PostgresStore) UserEntityEdges(userID string) ([]domain.UserEntityEdge, error) {
	rows, err := s.pool.Query(context.Background(),
		`SELECT user_id, entity_id, weight, confidence, source_context_id, visibility, sensitivity, updated_at
		 FROM llm_wiki_user_entity_edge WHERE user_id = $1`, userID)
	if err != nil {
		return nil, fmt.Errorf("user entity edges: %w", err)
	}
	defer rows.Close()
	var out []domain.UserEntityEdge
	for rows.Next() {
		var e domain.UserEntityEdge
		var srcCtxID *string
		if err := rows.Scan(&e.UserID, &e.EntityID, &e.Weight, &e.Confidence, &srcCtxID,
			&e.Visibility, &e.Sensitivity, &e.UpdatedAt); err != nil {
			return nil, err
		}
		if srcCtxID != nil {
			e.SourceContextID = *srcCtxID
		}
		out = append(out, e)
	}
	return out, rows.Err()
}

// ── UserContextSummary ──

func (s *PostgresStore) AddUserContextSummary(summary domain.UserContextSummary) error {
	if summary.ID == "" {
		summary.ID = domain.NewID("sum")
	}
	if summary.CreatedAt.IsZero() {
		summary.CreatedAt = time.Now()
	}
	if summary.UpdatedAt.IsZero() {
		summary.UpdatedAt = time.Now()
	}
	attrs, _ := json.Marshal(summary.Attrs)
	_, err := s.pool.Exec(context.Background(),
		`INSERT INTO llm_wiki_user_context_summary
		 (id, user_id, summary_type, text, attrs, source_context_ids,
		  confidence, sensitivity, visibility, purpose, version, created_at, updated_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)`,
		summary.ID, summary.UserID, summary.SummaryType, summary.Text, attrs,
		summary.SourceContextIDs, summary.Confidence, summary.Sensitivity,
		summary.Visibility, purposeToStrings(summary.Purpose), summary.Version,
		summary.CreatedAt, summary.UpdatedAt)
	if err != nil {
		return fmt.Errorf("add summary: %w", err)
	}
	return nil
}

func (s *PostgresStore) UserContextSummaries(userID string) ([]domain.UserContextSummary, error) {
	rows, err := s.pool.Query(context.Background(),
		`SELECT id, user_id, summary_type, text, attrs, source_context_ids,
		        confidence, sensitivity, visibility, purpose, version, created_at, updated_at
		 FROM llm_wiki_user_context_summary WHERE user_id = $1`, userID)
	if err != nil {
		return nil, fmt.Errorf("user summaries: %w", err)
	}
	defer rows.Close()
	var out []domain.UserContextSummary
	for rows.Next() {
		var s domain.UserContextSummary
		var attrs []byte
		var purposeStrs []string
		if err := rows.Scan(&s.ID, &s.UserID, &s.SummaryType, &s.Text, &attrs,
			&s.SourceContextIDs, &s.Confidence, &s.Sensitivity, &s.Visibility,
			&purposeStrs, &s.Version, &s.CreatedAt, &s.UpdatedAt); err != nil {
			return nil, err
		}
		json.Unmarshal(attrs, &s.Attrs)
		s.Purpose = stringsToPurposes(purposeStrs)
		out = append(out, s)
	}
	return out, rows.Err()
}

// ── ExtractionJob ──

func (s *PostgresStore) AddExtractionJob(job domain.ExtractionJob) error {
	if job.ID == "" {
		job.ID = domain.NewID("job")
	}
	if job.CreatedAt.IsZero() {
		job.CreatedAt = time.Now()
	}
	input, _ := json.Marshal(job.Input)
	output, _ := json.Marshal(job.Output)
	_, err := s.pool.Exec(context.Background(),
		`INSERT INTO llm_wiki_extraction_job
		 (id, user_id, source_asset_id, job_type, status, input, output, error,
		  model_provider, model_name, prompt_version, started_at, finished_at, created_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)`,
		job.ID, job.UserID, job.SourceAssetID, job.JobType, job.Status,
		input, output, job.Error,
		job.ModelProvider, job.ModelName, job.PromptVersion,
		job.StartedAt, job.FinishedAt, job.CreatedAt)
	if err != nil {
		return fmt.Errorf("add extraction job: %w", err)
	}
	return nil
}

func (s *PostgresStore) UpdateExtractionJob(id string, update func(*domain.ExtractionJob) error) (*domain.ExtractionJob, error) {
	// Read-modify-write via row lock
	tx, err := s.pool.Begin(context.Background())
	if err != nil {
		return nil, err
	}
	defer tx.Rollback(context.Background())

	var j domain.ExtractionJob
	var input, output []byte
	var srcAssetID *string
	err = tx.QueryRow(context.Background(),
		`SELECT id, user_id, source_asset_id, job_type, status, input, output, error,
		        model_provider, model_name, prompt_version, started_at, finished_at, created_at
		 FROM llm_wiki_extraction_job WHERE id = $1 FOR UPDATE`, id).
		Scan(&j.ID, &j.UserID, &srcAssetID, &j.JobType, &j.Status, &input, &output, &j.Error,
			&j.ModelProvider, &j.ModelName, &j.PromptVersion, &j.StartedAt, &j.FinishedAt, &j.CreatedAt)
	if err != nil {
		return nil, fmt.Errorf("extraction job %q: %w", id, err)
	}
	if srcAssetID != nil {
		j.SourceAssetID = *srcAssetID
	}
	json.Unmarshal(input, &j.Input)
	json.Unmarshal(output, &j.Output)

	if update != nil {
		if err := update(&j); err != nil {
			return nil, err
		}
	}

	newInput, _ := json.Marshal(j.Input)
	newOutput, _ := json.Marshal(j.Output)
	_, err = tx.Exec(context.Background(),
		`UPDATE llm_wiki_extraction_job SET
		   status = $2, output = $3, error = $4, finished_at = $5
		 WHERE id = $1`,
		j.ID, j.Status, newOutput, j.Error, j.FinishedAt)
	if err != nil {
		return nil, err
	}
	if err := tx.Commit(context.Background()); err != nil {
		return nil, err
	}
	return &j, nil
}

func (s *PostgresStore) ExtractionJobsByUser(userID string) ([]domain.ExtractionJob, error) {
	rows, err := s.pool.Query(context.Background(),
		`SELECT id, user_id, source_asset_id, job_type, status, input, output, error,
		        model_provider, model_name, prompt_version, started_at, finished_at, created_at
		 FROM llm_wiki_extraction_job WHERE user_id = $1 ORDER BY created_at DESC`, userID)
	if err != nil {
		return nil, fmt.Errorf("extraction jobs: %w", err)
	}
	defer rows.Close()
	var out []domain.ExtractionJob
	for rows.Next() {
		var j domain.ExtractionJob
		var input, output []byte
		var srcAssetID, errStr, mp, mn, pv *string
		if err := rows.Scan(&j.ID, &j.UserID, &srcAssetID, &j.JobType, &j.Status,
			&input, &output, &errStr, &mp, &mn, &pv,
			&j.StartedAt, &j.FinishedAt, &j.CreatedAt); err != nil {
			return nil, err
		}
		if srcAssetID != nil {
			j.SourceAssetID = *srcAssetID
		}
		json.Unmarshal(input, &j.Input)
		json.Unmarshal(output, &j.Output)
		if errStr != nil {
			j.Error = *errStr
		}
		if mp != nil {
			j.ModelProvider = *mp
		}
		if mn != nil {
			j.ModelName = *mn
		}
		if pv != nil {
			j.PromptVersion = *pv
		}
		out = append(out, j)
	}
	return out, rows.Err()
}

// ── helpers (add to postgres.go) ──

func purposeToStrings(purposes []domain.Purpose) []string {
	out := make([]string, len(purposes))
	for i, p := range purposes {
		out[i] = string(p)
	}
	return out
}

func stringsToPurposes(ss []string) []domain.Purpose {
	out := make([]domain.Purpose, len(ss))
	for i, s := range ss {
		out[i] = domain.Purpose(s)
	}
	return out
}
```

- [ ] **Step 2: 验证编译**

```bash
go build ./...
```

Expected: 编译通过。

- [ ] **Step 3: Commit**

```bash
git add internal/repository/entity_postgres.go
git commit -m "feat(repo): implement Entity/Edge/Summary/Job for postgres backend"
```

---

### Task 6: Postgres 集成测试

**Files:**
- Modify: `internal/repository/postgres_integration_test.go`

- [ ] **Step 1: 新增集成测试**

在看当前 `postgres_integration_test.go` 结构后，追加测试函数：

```go
func TestEntityCRUD(t *testing.T) {
	if os.Getenv("RUN_PSQL_TESTS") != "1" {
		t.Skip("set RUN_PSQL_TESTS=1 to run postgres integration tests")
	}
	store := openTestPostgres(t)
	e := domain.Entity{EntityType: "interest", Name: "AI"}
	if err := store.AddEntity(e); err != nil {
		t.Fatal(err)
	}
	got, err := store.EntityByID(e.ID)
	if err != nil {
		t.Fatal(err)
	}
	if got.Name != "AI" {
		t.Errorf("expected AI, got %s", got.Name)
	}
}

func TestUserEntityEdgeUpsert(t *testing.T) {
	if os.Getenv("RUN_PSQL_TESTS") != "1" {
		t.Skip("set RUN_PSQL_TESTS=1")
	}
	store := openTestPostgres(t)
	edge := domain.UserEntityEdge{UserID: "u1", EntityID: "e1", Weight: 0.8, Visibility: domain.VisibilityPrivate}
	if err := store.UpsertUserEntityEdge(edge); err != nil {
		t.Fatal(err)
	}
	edges, err := store.UserEntityEdges("u1")
	if err != nil {
		t.Fatal(err)
	}
	if len(edges) != 1 || edges[0].Weight != 0.8 {
		t.Fatalf("unexpected edges: %+v", edges)
	}
}

func TestUserContextSummaryCRUD(t *testing.T) {
	if os.Getenv("RUN_PSQL_TESTS") != "1" {
		t.Skip("set RUN_PSQL_TESTS=1")
	}
	store := openTestPostgres(t)
	summary := domain.UserContextSummary{
		UserID: "u1", SummaryType: "stable", Text: "test summary",
		Visibility: domain.VisibilityPrivate, Sensitivity: domain.SensitivityNormal,
	}
	if err := store.AddUserContextSummary(summary); err != nil {
		t.Fatal(err)
	}
	sums, err := store.UserContextSummaries("u1")
	if err != nil {
		t.Fatal(err)
	}
	if len(sums) != 1 {
		t.Fatalf("expected 1 summary, got %d", len(sums))
	}
}

func TestExtractionJobCRUD(t *testing.T) {
	if os.Getenv("RUN_PSQL_TESTS") != "1" {
		t.Skip("set RUN_PSQL_TESTS=1")
	}
	store := openTestPostgres(t)
	job := domain.ExtractionJob{UserID: "u1", JobType: "vision", Status: "pending"}
	if err := store.AddExtractionJob(job); err != nil {
		t.Fatal(err)
	}
	updated, err := store.UpdateExtractionJob(job.ID, func(j *domain.ExtractionJob) error {
		j.Status = "succeeded"
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
	if updated.Status != "succeeded" {
		t.Errorf("expected succeeded, got %s", updated.Status)
	}
}

func TestExtractionJobsByUser(t *testing.T) {
	if os.Getenv("RUN_PSQL_TESTS") != "1" {
		t.Skip("set RUN_PSQL_TESTS=1")
	}
	store := openTestPostgres(t)
	jobs, err := store.ExtractionJobsByUser("u1")
	if err != nil {
		t.Fatal(err)
	}
	if len(jobs) < 1 {
		t.Fatal("expected at least 1 job from previous test")
	}
}
```

- [ ] **Step 2: 运行集成测试（如果 postgres 可用）**

```bash
RUN_PSQL_TESTS=1 go test ./internal/repository/ -run "TestEntity|TestUser|TestExtraction" -v
```

Expected: 如果有 postgres 则 PASS，否则 SKIP。

- [ ] **Step 3: Commit**

```bash
git add internal/repository/postgres_integration_test.go
git commit -m "test(repo): add postgres integration tests for Entity/Edge/Summary/Job"
```

---

### Task 7: 全量回归

**Files:** (run-only)

- [ ] **Step 1: 全部测试**

```bash
go test ./... -count=1 -v 2>&1 | tail -30
```

- [ ] **Step 2: 验证 demo flow 无回归**

```bash
go run ./cmd/ctx --data $(mktemp -d) demo run 2>&1 | grep -E "Demo data ready|Bridge:|Model Call"
```

- [ ] **Step 3: Build both binaries**

```bash
go build ./cmd/ctx/ ./cmd/ctx-web/ && echo "both build ok"
```

- [ ] **Step 4: Commit (如有遗留修改)**

```bash
git status --short
```

---

### 验收标准

1. `go test ./...` 全部通过
2. 4 个新 domain 类型：Entity, UserEntityEdge, UserContextSummary, ExtractionJob
3. 9 个新 Repository 方法：Add/Upsert/List 系列
4. file 后端 state.json 可读写新类型
5. postgres schema 包含 4 张新表
6. postgres CRUD 集成测试通过
7. `ctx demo run` 无回归
