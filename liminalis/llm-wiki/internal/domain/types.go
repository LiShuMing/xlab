package domain

import (
	"crypto/rand"
	"encoding/hex"
	"strings"
	"time"
)

type Visibility string

const (
	VisibilityPrivate    Visibility = "private"
	VisibilityMatchOnly  Visibility = "match_only"
	VisibilityFriendOnly Visibility = "friend_only"
	VisibilityPublic     Visibility = "public"
	VisibilityBlocked    Visibility = "blocked"
)

type Purpose string

const (
	PurposeSelfMemory     Purpose = "self_memory"
	PurposeMatching       Purpose = "matching"
	PurposeRecommendation Purpose = "recommendation"
	PurposeGeneration     Purpose = "generation"
	PurposeTraining       Purpose = "training"
)

type Sensitivity int

const (
	SensitivityLow Sensitivity = iota
	SensitivityNormal
	SensitivitySensitive
	SensitivityHighlySensitive
)

type ContextState string

const (
	StateDraft         ContextState = "draft"
	StatePendingReview ContextState = "pending_review"
	StateActive        ContextState = "active"
	StateRejected      ContextState = "rejected"
	StateExpired       ContextState = "expired"
	StateDeleted       ContextState = "deleted"
)

type ReviewStatus string

const (
	ReviewUnreviewed ReviewStatus = "unreviewed"
	ReviewApproved   ReviewStatus = "approved"
	ReviewRejected   ReviewStatus = "rejected"
)

type User struct {
	ID          string    `json:"id"`
	Handle      string    `json:"handle"`
	DisplayName string    `json:"display_name"`
	City        string    `json:"city"`
	ProfileText string    `json:"profile_text"`
	CreatedAt   time.Time `json:"created_at"`
	UpdatedAt   time.Time `json:"updated_at"`
}

type SourceAsset struct {
	ID               string         `json:"id"`
	UserID           string         `json:"user_id"`
	AssetType        string         `json:"asset_type"`
	URI              string         `json:"uri"`
	SHA256           string         `json:"sha256"`
	OriginalFilename string         `json:"original_filename"`
	Text             string         `json:"text,omitempty"`
	Metadata         map[string]any `json:"metadata"`
	Visibility       Visibility     `json:"visibility"`
	Sensitivity      Sensitivity    `json:"sensitivity"`
	State            string         `json:"state"`
	ObservedAt       *time.Time     `json:"observed_at,omitempty"`
	CreatedAt        time.Time      `json:"created_at"`
}

type ContextItem struct {
	ID               string         `json:"id"`
	UserID           string         `json:"user_id"`
	Type             string         `json:"type"`
	Text             string         `json:"text"`
	Attrs            map[string]any `json:"attrs"`
	SourceType       string         `json:"source_type"`
	SourceAssetID    string         `json:"source_asset_id,omitempty"`
	SourceContextIDs []string       `json:"source_context_ids"`
	Confidence       float64        `json:"confidence"`
	SourceTrust      float64        `json:"source_trust"`
	Sensitivity      Sensitivity    `json:"sensitivity"`
	Visibility       Visibility     `json:"visibility"`
	Purpose          []Purpose      `json:"purpose"`
	State            ContextState   `json:"state"`
	ReviewStatus     ReviewStatus   `json:"review_status"`
	ObservedAt       *time.Time     `json:"observed_at,omitempty"`
	ExpiresAt        *time.Time     `json:"expires_at,omitempty"`
	DeletedAt        *time.Time     `json:"deleted_at,omitempty"`
	ModelProvider    string         `json:"model_provider,omitempty"`
	ModelVersion     string         `json:"model_version,omitempty"`
	PromptVersion    string         `json:"prompt_version,omitempty"`
	CreatedAt        time.Time      `json:"created_at"`
	UpdatedAt        time.Time      `json:"updated_at"`
}

type UsageAudit struct {
	ID           string    `json:"id"`
	ContextID    string    `json:"context_id"`
	UserID       string    `json:"user_id"`
	UsedBy       string    `json:"used_by"`
	Purpose      Purpose   `json:"purpose"`
	TargetUserID string    `json:"target_user_id,omitempty"`
	Allowed      bool      `json:"allowed"`
	Reason       string    `json:"reason"`
	CreatedAt    time.Time `json:"created_at"`
}

type ModelCallLog struct {
	ID            string    `json:"id"`
	UserID        string    `json:"user_id,omitempty"`
	Provider      string    `json:"provider"`
	Model         string    `json:"model"`
	TaskType      string    `json:"task_type"`
	InputTokens   int       `json:"input_tokens,omitempty"`
	OutputTokens  int       `json:"output_tokens,omitempty"`
	ImageCount    int       `json:"image_count,omitempty"`
	CostEstimated float64   `json:"cost_estimated,omitempty"`
	LatencyMS     int64     `json:"latency_ms"`
	Status        string    `json:"status"`
	Error         string    `json:"error,omitempty"`
	CreatedAt     time.Time `json:"created_at"`
}

type ContextVector struct {
	ID             string      `json:"id"`
	ContextID      string      `json:"context_id"`
	UserID         string      `json:"user_id"`
	VectorType     string      `json:"vector_type"`
	Embedding      []float64   `json:"embedding"`
	EmbeddingModel string      `json:"embedding_model"`
	Visibility     Visibility  `json:"visibility"`
	Sensitivity    Sensitivity `json:"sensitivity"`
	CreatedAt      time.Time   `json:"created_at"`
}

type MatchResult struct {
	ID               string         `json:"id"`
	UserID           string         `json:"user_id"`
	TargetUserID     string         `json:"target_user_id"`
	Score            float64        `json:"score"`
	ScoreBreakdown   map[string]any `json:"score_breakdown"`
	ContextIDs       []string       `json:"context_ids"`
	SafeContextPack  map[string]any `json:"safe_context_pack"`
	BridgeResult     map[string]any `json:"bridge_result"`
	PrivacyCheck     map[string]any `json:"privacy_check"`
	CreatedAt        time.Time      `json:"created_at"`
	TargetHandle     string         `json:"target_handle,omitempty"`
	TargetName       string         `json:"target_name,omitempty"`
	ConnectionReason string         `json:"connection_reason,omitempty"`
	Icebreakers      []string       `json:"icebreakers,omitempty"`
}

type PolicyDecision struct {
	Allowed bool
	Reason  string
}

func NewID(prefix string) string {
	var b [8]byte
	if _, err := rand.Read(b[:]); err != nil {
		return prefix + "_" + strings.ReplaceAll(time.Now().Format("20060102150405.000000000"), ".", "")
	}
	return prefix + "_" + hex.EncodeToString(b[:])
}

func ContainsPurpose(items []Purpose, purpose Purpose) bool {
	for _, item := range items {
		if item == purpose {
			return true
		}
	}
	return false
}

func ParsePurposes(raw string, fallback []Purpose) []Purpose {
	if strings.TrimSpace(raw) == "" {
		return fallback
	}
	parts := strings.Split(raw, ",")
	out := make([]Purpose, 0, len(parts))
	seen := map[Purpose]bool{}
	for _, part := range parts {
		p := Purpose(strings.TrimSpace(part))
		if p == "" || seen[p] {
			continue
		}
		seen[p] = true
		out = append(out, p)
	}
	if len(out) == 0 {
		return fallback
	}
	return out
}

func ParseVisibility(raw string, fallback Visibility) Visibility {
	switch Visibility(strings.TrimSpace(raw)) {
	case VisibilityPrivate, VisibilityMatchOnly, VisibilityFriendOnly, VisibilityPublic, VisibilityBlocked:
		return Visibility(strings.TrimSpace(raw))
	default:
		return fallback
	}
}
