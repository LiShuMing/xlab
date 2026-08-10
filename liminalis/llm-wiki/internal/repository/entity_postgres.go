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
	purposeStrs := make([]string, len(summary.Purpose))
	for i, p := range summary.Purpose {
		purposeStrs[i] = string(p)
	}
	_, err := s.pool.Exec(context.Background(),
		`INSERT INTO llm_wiki_user_context_summary
		 (id, user_id, summary_type, text, attrs, source_context_ids,
		  confidence, sensitivity, visibility, purpose, version, created_at, updated_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)`,
		summary.ID, summary.UserID, summary.SummaryType, summary.Text, attrs,
		summary.SourceContextIDs, summary.Confidence, summary.Sensitivity,
		summary.Visibility, purposeStrs, summary.Version,
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
		var su domain.UserContextSummary
		var attrs []byte
		var purposeStrs []string
		if err := rows.Scan(&su.ID, &su.UserID, &su.SummaryType, &su.Text, &attrs,
			&su.SourceContextIDs, &su.Confidence, &su.Sensitivity, &su.Visibility,
			&purposeStrs, &su.Version, &su.CreatedAt, &su.UpdatedAt); err != nil {
			return nil, err
		}
		json.Unmarshal(attrs, &su.Attrs)
		su.Purpose = make([]domain.Purpose, len(purposeStrs))
		for i, s := range purposeStrs {
			su.Purpose[i] = domain.Purpose(s)
		}
		out = append(out, su)
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
