package repository

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/LiShuMing/xlab/liminalis/llm-wiki/internal/config"
	"github.com/LiShuMing/xlab/liminalis/llm-wiki/internal/domain"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/jackc/pgx/v5/pgxpool"
)

type PostgresStore struct {
	pool        *pgxpool.Pool
	databaseURL string
	dataDir     string
}

func OpenPostgres(opts Options) (Repository, error) {
	config.LoadDotEnv("")
	databaseURL := strings.TrimSpace(opts.DatabaseURL)
	if databaseURL == "" {
		databaseURL = postgresURLFromEnv()
	}
	if databaseURL == "" {
		return nil, fmt.Errorf("postgres repository backend requires --database-url or PSQL_URL/PSQL_USER/PSQL_PASSWORD in ~/.env")
	}
	pool, err := pgxpool.New(context.Background(), databaseURL)
	if err != nil {
		return nil, err
	}
	store := &PostgresStore{
		pool:        pool,
		databaseURL: databaseURL,
		dataDir:     opts.DataDir,
	}
	if store.dataDir == "" {
		store.dataDir = "data"
	}
	return store, nil
}

func (s *PostgresStore) Init() error {
	if err := os.MkdirAll(filepath.Join(s.dataDir, "assets"), 0o755); err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Join(s.dataDir, "processed"), 0o755); err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Join(s.dataDir, "exports"), 0o755); err != nil {
		return err
	}
	_, err := s.pool.Exec(context.Background(), postgresSchema)
	return err
}

func (s *PostgresStore) Describe() string {
	parsed, err := url.Parse(s.databaseURL)
	if err != nil {
		return "postgres:<configured>"
	}
	db := strings.TrimPrefix(parsed.Path, "/")
	if db == "" {
		db = "<database>"
	}
	return "postgres:" + parsed.Host + "/" + db
}

func (s *PostgresStore) DataDirPath() string {
	return s.dataDir
}

func (s *PostgresStore) UserByHandle(handle string) (*domain.User, error) {
	var doc []byte
	err := s.pool.QueryRow(context.Background(), `SELECT doc FROM llm_wiki_app_user WHERE handle=$1`, handle).Scan(&doc)
	if err != nil {
		return nil, notFound(err, fmt.Sprintf("user %q not found", handle))
	}
	var user domain.User
	if err := json.Unmarshal(doc, &user); err != nil {
		return nil, err
	}
	return &user, nil
}

func (s *PostgresStore) UserByID(id string) (*domain.User, error) {
	var doc []byte
	err := s.pool.QueryRow(context.Background(), `SELECT doc FROM llm_wiki_app_user WHERE id=$1`, id).Scan(&doc)
	if err != nil {
		return nil, notFound(err, fmt.Sprintf("user id %q not found", id))
	}
	var user domain.User
	if err := json.Unmarshal(doc, &user); err != nil {
		return nil, err
	}
	return &user, nil
}

func (s *PostgresStore) ListUsers() []domain.User {
	rows, err := s.pool.Query(context.Background(), `SELECT doc FROM llm_wiki_app_user ORDER BY created_at`)
	if err != nil {
		return nil
	}
	defer rows.Close()
	var users []domain.User
	for rows.Next() {
		var user domain.User
		if scanJSON(rows, &user) == nil {
			users = append(users, user)
		}
	}
	return users
}

func (s *PostgresStore) AddUser(user domain.User) error {
	doc, err := json.Marshal(user)
	if err != nil {
		return err
	}
	_, err = s.pool.Exec(
		context.Background(),
		`INSERT INTO llm_wiki_app_user (id, handle, doc, created_at, updated_at)
		 VALUES ($1, $2, $3, $4, $5)`,
		user.ID, user.Handle, doc, user.CreatedAt, user.UpdatedAt,
	)
	if isUniqueViolation(err) {
		return fmt.Errorf("user %q already exists", user.Handle)
	}
	return err
}

func (s *PostgresStore) AddAsset(asset domain.SourceAsset) error {
	if asset.SHA256 != "" {
		var existing string
		err := s.pool.QueryRow(
			context.Background(),
			`SELECT id FROM llm_wiki_source_asset WHERE user_id=$1 AND sha256=$2 LIMIT 1`,
			asset.UserID, asset.SHA256,
		).Scan(&existing)
		if err == nil {
			return fmt.Errorf("duplicate asset sha256=%s", asset.SHA256)
		}
		if !errors.Is(err, pgx.ErrNoRows) {
			return err
		}
	}
	doc, err := json.Marshal(asset)
	if err != nil {
		return err
	}
	_, err = s.pool.Exec(
		context.Background(),
		`INSERT INTO llm_wiki_source_asset (id, user_id, asset_type, sha256, state, doc, created_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7)`,
		asset.ID, asset.UserID, asset.AssetType, asset.SHA256, asset.State, doc, asset.CreatedAt,
	)
	return err
}

func (s *PostgresStore) AssetByID(id string) (*domain.SourceAsset, error) {
	var doc []byte
	err := s.pool.QueryRow(context.Background(), `SELECT doc FROM llm_wiki_source_asset WHERE id=$1`, id).Scan(&doc)
	if err != nil {
		return nil, notFound(err, fmt.Sprintf("asset %q not found", id))
	}
	var asset domain.SourceAsset
	if err := json.Unmarshal(doc, &asset); err != nil {
		return nil, err
	}
	return &asset, nil
}

func (s *PostgresStore) AssetsByUser(userID string) []domain.SourceAsset {
	rows, err := s.pool.Query(context.Background(), `SELECT doc FROM llm_wiki_source_asset WHERE user_id=$1 ORDER BY created_at`, userID)
	if err != nil {
		return nil
	}
	defer rows.Close()
	var assets []domain.SourceAsset
	for rows.Next() {
		var asset domain.SourceAsset
		if scanJSON(rows, &asset) == nil {
			assets = append(assets, asset)
		}
	}
	return assets
}

func (s *PostgresStore) AddContext(item domain.ContextItem) error {
	doc, err := json.Marshal(item)
	if err != nil {
		return err
	}
	_, err = s.pool.Exec(
		context.Background(),
		`INSERT INTO llm_wiki_context_item
		 (id, user_id, type, state, visibility, sensitivity, source_asset_id, doc, created_at, updated_at)
		 VALUES ($1, $2, $3, $4, $5, $6, NULLIF($7, ''), $8, $9, $10)`,
		item.ID, item.UserID, item.Type, item.State, item.Visibility, item.Sensitivity, item.SourceAssetID, doc, item.CreatedAt, item.UpdatedAt,
	)
	return err
}

func (s *PostgresStore) ContextByID(id string) (*domain.ContextItem, error) {
	var doc []byte
	err := s.pool.QueryRow(context.Background(), `SELECT doc FROM llm_wiki_context_item WHERE id=$1`, id).Scan(&doc)
	if err != nil {
		return nil, notFound(err, fmt.Sprintf("context %q not found", id))
	}
	var item domain.ContextItem
	if err := json.Unmarshal(doc, &item); err != nil {
		return nil, err
	}
	return &item, nil
}

func (s *PostgresStore) UpdateContext(id string, update func(*domain.ContextItem) error) (*domain.ContextItem, error) {
	ctx, err := s.ContextByID(id)
	if err != nil {
		return nil, err
	}
	if update != nil {
		if err := update(ctx); err != nil {
			return nil, err
		}
	}
	doc, err := json.Marshal(ctx)
	if err != nil {
		return nil, err
	}
	_, err = s.pool.Exec(
		context.Background(),
		`UPDATE llm_wiki_context_item
		 SET state=$2, visibility=$3, sensitivity=$4, doc=$5, updated_at=$6
		 WHERE id=$1`,
		ctx.ID, ctx.State, ctx.Visibility, ctx.Sensitivity, doc, ctx.UpdatedAt,
	)
	if err != nil {
		return nil, err
	}
	return ctx, nil
}

func (s *PostgresStore) ContextsByUser(userID string) []domain.ContextItem {
	rows, err := s.pool.Query(context.Background(), `SELECT doc FROM llm_wiki_context_item WHERE user_id=$1 ORDER BY created_at DESC`, userID)
	if err != nil {
		return nil
	}
	defer rows.Close()
	var contexts []domain.ContextItem
	for rows.Next() {
		var item domain.ContextItem
		if scanJSON(rows, &item) == nil {
			contexts = append(contexts, item)
		}
	}
	return contexts
}

func (s *PostgresStore) AllContexts() []domain.ContextItem {
	rows, err := s.pool.Query(context.Background(), `SELECT doc FROM llm_wiki_context_item ORDER BY created_at DESC`)
	if err != nil {
		return nil
	}
	defer rows.Close()
	var contexts []domain.ContextItem
	for rows.Next() {
		var item domain.ContextItem
		if scanJSON(rows, &item) == nil {
			contexts = append(contexts, item)
		}
	}
	return contexts
}

func (s *PostgresStore) AddContextVector(vector domain.ContextVector) error {
	doc, err := json.Marshal(vector)
	if err != nil {
		return err
	}
	_, err = s.pool.Exec(
		context.Background(),
		`INSERT INTO llm_wiki_context_vector
		 (id, context_id, user_id, vector_type, embedding_model, visibility, sensitivity, doc, created_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
		 ON CONFLICT (context_id, vector_type)
		 DO UPDATE SET embedding_model=EXCLUDED.embedding_model,
		               visibility=EXCLUDED.visibility,
		               sensitivity=EXCLUDED.sensitivity,
		               doc=EXCLUDED.doc,
		               created_at=EXCLUDED.created_at`,
		vector.ID, vector.ContextID, vector.UserID, vector.VectorType, vector.EmbeddingModel, vector.Visibility, vector.Sensitivity, doc, vector.CreatedAt,
	)
	return err
}

func (s *PostgresStore) ContextVectorsByUser(userID string) []domain.ContextVector {
	rows, err := s.pool.Query(context.Background(), `SELECT doc FROM llm_wiki_context_vector WHERE user_id=$1 ORDER BY created_at`, userID)
	if err != nil {
		return nil
	}
	defer rows.Close()
	var vectors []domain.ContextVector
	for rows.Next() {
		var vector domain.ContextVector
		if scanJSON(rows, &vector) == nil {
			vectors = append(vectors, vector)
		}
	}
	return vectors
}

func (s *PostgresStore) ContextVectorByContextID(contextID string) (*domain.ContextVector, error) {
	var doc []byte
	err := s.pool.QueryRow(context.Background(), `SELECT doc FROM llm_wiki_context_vector WHERE context_id=$1 AND vector_type='text'`, contextID).Scan(&doc)
	if err != nil {
		return nil, notFound(err, fmt.Sprintf("context vector for %q not found", contextID))
	}
	var vector domain.ContextVector
	if err := json.Unmarshal(doc, &vector); err != nil {
		return nil, err
	}
	return &vector, nil
}

func (s *PostgresStore) AddAudit(audit domain.UsageAudit) error {
	doc, err := json.Marshal(audit)
	if err != nil {
		return err
	}
	_, err = s.pool.Exec(
		context.Background(),
		`INSERT INTO llm_wiki_context_usage_audit
		 (id, context_id, user_id, used_by, purpose, allowed, doc, created_at)
		 VALUES ($1, NULLIF($2, ''), $3, $4, $5, $6, $7, $8)`,
		audit.ID, audit.ContextID, audit.UserID, audit.UsedBy, audit.Purpose, audit.Allowed, doc, audit.CreatedAt,
	)
	return err
}

func (s *PostgresStore) AddModelCall(call domain.ModelCallLog) error {
	doc, err := json.Marshal(call)
	if err != nil {
		return err
	}
	_, err = s.pool.Exec(
		context.Background(),
		`INSERT INTO llm_wiki_model_call_log
		 (id, user_id, provider, model, task_type, status, latency_ms, doc, created_at)
		 VALUES ($1, NULLIF($2, ''), $3, $4, $5, $6, $7, $8, $9)`,
		call.ID, call.UserID, call.Provider, call.Model, call.TaskType, call.Status, call.LatencyMS, doc, call.CreatedAt,
	)
	return err
}

func (s *PostgresStore) ModelCalls() []domain.ModelCallLog {
	rows, err := s.pool.Query(context.Background(), `SELECT doc FROM llm_wiki_model_call_log ORDER BY created_at`)
	if err != nil {
		return nil
	}
	defer rows.Close()
	var calls []domain.ModelCallLog
	for rows.Next() {
		var call domain.ModelCallLog
		if scanJSON(rows, &call) == nil {
			calls = append(calls, call)
		}
	}
	return calls
}

func (s *PostgresStore) AddMatch(match domain.MatchResult) error {
	doc, err := json.Marshal(match)
	if err != nil {
		return err
	}
	_, err = s.pool.Exec(
		context.Background(),
		`INSERT INTO llm_wiki_match_result
		 (id, user_id, target_user_id, score, doc, created_at)
		 VALUES ($1, $2, $3, $4, $5, $6)`,
		match.ID, match.UserID, match.TargetUserID, match.Score, doc, match.CreatedAt,
	)
	return err
}

func (s *PostgresStore) MatchesByUser(userID string) []domain.MatchResult {
	rows, err := s.pool.Query(context.Background(), `SELECT doc FROM llm_wiki_match_result WHERE user_id = $1 ORDER BY created_at DESC`, userID)
	if err != nil {
		return nil
	}
	defer rows.Close()
	var matches []domain.MatchResult
	for rows.Next() {
		var match domain.MatchResult
		if scanJSON(rows, &match) == nil {
			matches = append(matches, match)
		}
	}
	return matches
}

// DeleteContextVector removes the vector for a given context. Idempotent.
func (s *PostgresStore) DeleteContextVector(contextID string) error {
	_, err := s.pool.Exec(context.Background(),
		`DELETE FROM llm_wiki_context_vector WHERE context_id = $1`,
		contextID,
	)
	return err
}

// DeleteMatchesByContextID removes all match_result rows whose context_ids JSONB array
// contains the given contextID.
func (s *PostgresStore) DeleteMatchesByContextID(contextID string) error {
	_, err := s.pool.Exec(context.Background(),
		`DELETE FROM llm_wiki_match_result WHERE doc->'context_ids' ? $1`,
		contextID,
	)
	return err
}

// DeleteSummariesBySourceContextID removes all summaries whose source_context_ids
// native TEXT array contains the given contextID.
func (s *PostgresStore) DeleteSummariesBySourceContextID(contextID string) error {
	_, err := s.pool.Exec(context.Background(),
		`DELETE FROM llm_wiki_user_context_summary WHERE $1 = ANY(source_context_ids)`,
		contextID,
	)
	return err
}

// DeleteJobsByContextID removes all extraction jobs whose input references the
// given contextID.
func (s *PostgresStore) DeleteJobsByContextID(contextID string) error {
	_, err := s.pool.Exec(context.Background(),
		`DELETE FROM llm_wiki_extraction_job WHERE input->>'context_id' = $1`,
		contextID,
	)
	return err
}

// DeleteContextsByAssetID removes all non-deleted context items for an asset and
// returns the removed items for cascade purposes.
func (s *PostgresStore) DeleteContextsByAssetID(assetID string) ([]domain.ContextItem, error) {
	rows, err := s.pool.Query(context.Background(),
		`DELETE FROM llm_wiki_context_item
		 WHERE doc->>'source_asset_id' = $1 AND doc->>'state' != 'deleted'
		 RETURNING doc`,
		assetID,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var contexts []domain.ContextItem
	for rows.Next() {
		var item domain.ContextItem
		if err := scanJSON(rows, &item); err != nil {
			return nil, err
		}
		contexts = append(contexts, item)
	}
	return contexts, nil
}

// DeleteAsset removes an asset by ID and returns it.
func (s *PostgresStore) DeleteAsset(id string) (*domain.SourceAsset, error) {
	var doc []byte
	err := s.pool.QueryRow(context.Background(),
		`DELETE FROM llm_wiki_source_asset WHERE id = $1 RETURNING doc`,
		id,
	).Scan(&doc)
	if err != nil {
		return nil, notFound(err, fmt.Sprintf("asset %q not found", id))
	}
	var asset domain.SourceAsset
	if err := json.Unmarshal(doc, &asset); err != nil {
		return nil, err
	}
	return &asset, nil
}

// FindExpiredContexts returns all active contexts whose expires_at is non-nil
// and at or before the given time. Does not modify state.
func (s *PostgresStore) FindExpiredContexts(now time.Time) ([]domain.ContextItem, error) {
	rows, err := s.pool.Query(context.Background(),
		`SELECT doc FROM llm_wiki_context_item
		 WHERE doc->>'expires_at' IS NOT NULL
		   AND (doc->>'expires_at')::timestamptz <= $1
		   AND doc->>'state' = 'active'`,
		now,
	)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var contexts []domain.ContextItem
	for rows.Next() {
		var item domain.ContextItem
		if err := scanJSON(rows, &item); err != nil {
			return nil, err
		}
		contexts = append(contexts, item)
	}
	return contexts, nil
}

func scanJSON(rows pgx.Rows, dest any) error {
	var doc []byte
	if err := rows.Scan(&doc); err != nil {
		return err
	}
	return json.Unmarshal(doc, dest)
}

func notFound(err error, msg string) error {
	if errors.Is(err, pgx.ErrNoRows) {
		return fmt.Errorf("%s", msg)
	}
	return err
}

func isUniqueViolation(err error) bool {
	var pgErr *pgconn.PgError
	return errors.As(err, &pgErr) && pgErr.Code == "23505"
}

func postgresURLFromEnv() string {
	raw := strings.TrimSpace(os.Getenv("PSQL_URL"))
	if raw == "" {
		return ""
	}
	if strings.HasPrefix(raw, "postgres://") || strings.HasPrefix(raw, "postgresql://") {
		return raw
	}
	user := strings.TrimSpace(os.Getenv("PSQL_USER"))
	password := os.Getenv("PSQL_PASSWORD")
	port := strings.TrimSpace(os.Getenv("PSQL_PORT"))
	db := strings.TrimSpace(os.Getenv("PSQL_DEFAULT_DB"))
	if user == "" || password == "" {
		return ""
	}
	if port == "" {
		port = "5432"
	}
	if db == "" {
		db = "postgres"
	}
	return "postgres://" + url.QueryEscape(user) + ":" + url.QueryEscape(password) + "@" + raw + ":" + port + "/" + url.PathEscape(db) + "?sslmode=prefer"
}

const postgresSchema = `
CREATE TABLE IF NOT EXISTS llm_wiki_app_user (
  id TEXT PRIMARY KEY,
  handle TEXT UNIQUE NOT NULL,
  doc JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS llm_wiki_source_asset (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES llm_wiki_app_user(id),
  asset_type TEXT NOT NULL,
  sha256 TEXT,
  state TEXT NOT NULL,
  doc JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_llm_wiki_asset_user ON llm_wiki_source_asset(user_id);
CREATE INDEX IF NOT EXISTS idx_llm_wiki_asset_sha ON llm_wiki_source_asset(user_id, sha256) WHERE sha256 IS NOT NULL AND sha256 <> '';

CREATE TABLE IF NOT EXISTS llm_wiki_context_item (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES llm_wiki_app_user(id),
  type TEXT NOT NULL,
  state TEXT NOT NULL,
  visibility TEXT NOT NULL,
  sensitivity SMALLINT NOT NULL,
  source_asset_id TEXT REFERENCES llm_wiki_source_asset(id),
  doc JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_llm_wiki_context_user_state ON llm_wiki_context_item(user_id, state);
CREATE INDEX IF NOT EXISTS idx_llm_wiki_context_visibility ON llm_wiki_context_item(visibility, sensitivity);

CREATE TABLE IF NOT EXISTS llm_wiki_context_vector (
  id TEXT PRIMARY KEY,
  context_id TEXT NOT NULL REFERENCES llm_wiki_context_item(id),
  user_id TEXT NOT NULL REFERENCES llm_wiki_app_user(id),
  vector_type TEXT NOT NULL,
  embedding_model TEXT NOT NULL,
  visibility TEXT NOT NULL,
  sensitivity SMALLINT NOT NULL,
  doc JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  UNIQUE(context_id, vector_type)
);
CREATE INDEX IF NOT EXISTS idx_llm_wiki_vector_user ON llm_wiki_context_vector(user_id, vector_type);

CREATE TABLE IF NOT EXISTS llm_wiki_context_usage_audit (
  id TEXT PRIMARY KEY,
  context_id TEXT,
  user_id TEXT NOT NULL,
  used_by TEXT NOT NULL,
  purpose TEXT NOT NULL,
  allowed BOOLEAN NOT NULL,
  doc JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_llm_wiki_audit_user ON llm_wiki_context_usage_audit(user_id, created_at);

CREATE TABLE IF NOT EXISTS llm_wiki_model_call_log (
  id TEXT PRIMARY KEY,
  user_id TEXT,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  task_type TEXT NOT NULL,
  status TEXT NOT NULL,
  latency_ms BIGINT NOT NULL DEFAULT 0,
  doc JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_llm_wiki_model_call_user ON llm_wiki_model_call_log(user_id, created_at);

CREATE TABLE IF NOT EXISTS llm_wiki_match_result (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES llm_wiki_app_user(id),
  target_user_id TEXT NOT NULL REFERENCES llm_wiki_app_user(id),
  score DOUBLE PRECISION NOT NULL,
  doc JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_llm_wiki_match_user ON llm_wiki_match_result(user_id, created_at);

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
`
