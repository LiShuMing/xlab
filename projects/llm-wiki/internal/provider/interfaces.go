package provider

import "github.com/LiShuMing/xlab/projects/llm-wiki/internal/domain"

type Provider interface {
	ExtractPhotoContext(filename string, metadata map[string]any) PhotoExtraction
	EmbedTexts(texts []string) EmbeddingResult
	GenerateBridge(aContexts, bContexts []domain.ContextItem) BridgeResult
	GenerateCompanionReply(userText string, contexts []domain.ContextItem) CompanionReply
	Name() string
}

type EmbeddingResult struct {
	Embeddings   [][]float64 `json:"embeddings"`
	Provider     string      `json:"provider,omitempty"`
	Model        string      `json:"model,omitempty"`
	FallbackUsed bool        `json:"fallback_used,omitempty"`
	Error        string      `json:"error,omitempty"`
	LatencyMS    int64       `json:"latency_ms,omitempty"`
}

type BridgeResult struct {
	ConnectionReason string   `json:"connection_reason"`
	Icebreakers      []string `json:"icebreakers"`
	Provider         string   `json:"provider,omitempty"`
	Model            string   `json:"model,omitempty"`
	FallbackUsed     bool     `json:"fallback_used,omitempty"`
	Error            string   `json:"error,omitempty"`
	LatencyMS        int64    `json:"latency_ms,omitempty"`
}

type CompanionReply struct {
	Text         string   `json:"text"`
	MemoryUsed   []string `json:"memory_used,omitempty"`
	Suggestions  []string `json:"suggestions,omitempty"`
	Provider     string   `json:"provider,omitempty"`
	Model        string   `json:"model,omitempty"`
	FallbackUsed bool     `json:"fallback_used,omitempty"`
	Error        string   `json:"error,omitempty"`
	LatencyMS    int64    `json:"latency_ms,omitempty"`
}
