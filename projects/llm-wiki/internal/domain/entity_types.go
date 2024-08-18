package domain

import "time"

type Entity struct {
	ID            string         `json:"id"`
	EntityType    string         `json:"entity_type"` // interest, place, activity, topic, object
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
	Status        string         `json:"status"`   // pending, running, succeeded, failed
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
