package provider

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"

	"github.com/LiShuMing/xlab/liminalis/llm-wiki/internal/domain"
)

type OpenAICompatibleProvider struct {
	mock             MockProvider
	BaseURL          string
	APIKey           string
	EmbeddingAPIKey  string
	Model            string
	EmbeddingModel   string
	EmbeddingBaseURL string
	Client           *http.Client
}

func NewOpenAICompatibleFromEnv() (OpenAICompatibleProvider, bool) {
	apiKey := firstNonEmpty(os.Getenv("LLM_API_KEY"), os.Getenv("OPENAI_API_KEY"), os.Getenv("API_KEY"))
	baseURL := firstNonEmpty(os.Getenv("LLM_BASE_URL"), "https://api.openai.com/v1")
	model := firstNonEmpty(os.Getenv("LLM_MODEL"), "gpt-4.1-mini")
	embeddingModel := firstNonEmpty(os.Getenv("LLM_EMBEDDING_MODEL"), "text-embedding-v4")
	embeddingBaseURL := firstNonEmpty(os.Getenv("LLM_EMBEDDING_BASE_URL"), defaultEmbeddingBaseURL(baseURL))
	embeddingAPIKey := firstNonEmpty(os.Getenv("LLM_EMBEDDING_API_KEY"), apiKey)
	if apiKey == "" {
		return OpenAICompatibleProvider{}, false
	}
	timeout := 60 * time.Second
	if raw := os.Getenv("LLM_TIMEOUT"); raw != "" {
		if seconds, err := time.ParseDuration(raw + "s"); err == nil {
			timeout = seconds
		}
	}
	return OpenAICompatibleProvider{
		BaseURL:          strings.TrimRight(baseURL, "/"),
		APIKey:           apiKey,
		EmbeddingAPIKey:  embeddingAPIKey,
		Model:            model,
		EmbeddingModel:   embeddingModel,
		EmbeddingBaseURL: strings.TrimRight(embeddingBaseURL, "/"),
		Client:           &http.Client{Timeout: timeout},
	}, true
}

func (p OpenAICompatibleProvider) Name() string {
	return "openai-compatible:" + p.Model
}

func (p OpenAICompatibleProvider) ExtractPhotoContext(filename string, metadata map[string]any) PhotoExtraction {
	result, err := p.extractPhotoContext(filename, metadata)
	if err != nil {
		fallback := p.mock.ExtractPhotoContext(filename, metadata)
		fallback.Confidence = 0.0
		return fallback
	}
	return result
}

func (p OpenAICompatibleProvider) EmbedTexts(texts []string) EmbeddingResult {
	start := time.Now()
	result, err := p.embedTexts(texts)
	if err != nil || len(result.Embeddings) != len(texts) {
		fallback := p.mock.EmbedTexts(texts)
		fallback.Provider = "openai-compatible"
		fallback.Model = p.EmbeddingModel
		fallback.FallbackUsed = true
		fallback.LatencyMS = time.Since(start).Milliseconds()
		if err != nil {
			fallback.Error = err.Error()
		} else {
			fallback.Error = "embedding_count_mismatch"
		}
		return fallback
	}
	result.Provider = "openai-compatible"
	result.Model = p.EmbeddingModel
	result.LatencyMS = time.Since(start).Milliseconds()
	return result
}

func (p OpenAICompatibleProvider) embedTexts(texts []string) (EmbeddingResult, error) {
	body := embeddingRequest{
		Model:          p.EmbeddingModel,
		Input:          texts,
		Dimensions:     1024,
		EncodingFormat: "float",
	}
	raw, err := json.Marshal(body)
	if err != nil {
		return EmbeddingResult{}, err
	}
	req, err := http.NewRequest(http.MethodPost, p.EmbeddingBaseURL+"/embeddings", bytes.NewReader(raw))
	if err != nil {
		return EmbeddingResult{}, err
	}
	req.Header.Set("Authorization", "Bearer "+p.EmbeddingAPIKey)
	req.Header.Set("Content-Type", "application/json")
	resp, err := p.Client.Do(req)
	if err != nil {
		return EmbeddingResult{}, err
	}
	defer resp.Body.Close()
	respBody, err := io.ReadAll(io.LimitReader(resp.Body, 8<<20))
	if err != nil {
		return EmbeddingResult{}, err
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return EmbeddingResult{}, fmt.Errorf("embedding status %d: %s", resp.StatusCode, sanitizeResponse(respBody))
	}
	var parsed embeddingResponse
	if err := json.Unmarshal(respBody, &parsed); err != nil {
		return EmbeddingResult{}, err
	}
	embeddings := make([][]float64, len(parsed.Data))
	for _, item := range parsed.Data {
		if item.Index < 0 || item.Index >= len(embeddings) {
			return EmbeddingResult{}, fmt.Errorf("embedding index out of range: %d", item.Index)
		}
		embeddings[item.Index] = item.Embedding
	}
	return EmbeddingResult{Embeddings: embeddings}, nil
}

func (p OpenAICompatibleProvider) GenerateBridge(aContexts, bContexts []domain.ContextItem) BridgeResult {
	start := time.Now()
	result, err := p.generateBridge(aContexts, bContexts)
	if err != nil || strings.TrimSpace(result.ConnectionReason) == "" || len(result.Icebreakers) == 0 {
		fallback := p.mock.GenerateBridge(aContexts, bContexts)
		fallback.Provider = "openai-compatible"
		fallback.Model = p.Model
		fallback.FallbackUsed = true
		fallback.LatencyMS = time.Since(start).Milliseconds()
		if err != nil {
			fallback.Error = err.Error()
		} else {
			fallback.Error = "empty_llm_bridge_result"
		}
		return fallback
	}
	result.Provider = "openai-compatible"
	result.Model = p.Model
	result.LatencyMS = time.Since(start).Milliseconds()
	return result
}

func (p OpenAICompatibleProvider) GenerateCompanionReply(userText string, contexts []domain.ContextItem) CompanionReply {
	start := time.Now()
	result, err := p.generateCompanionReply(userText, contexts)
	if err != nil || strings.TrimSpace(result.Text) == "" {
		result.Provider = "openai-compatible"
		result.Model = p.Model
		result.LatencyMS = time.Since(start).Milliseconds()
		if err != nil {
			result.Error = err.Error()
		} else {
			result.Error = "empty_llm_companion_result"
		}
		return result
	}
	result.Provider = "openai-compatible"
	result.Model = p.Model
	result.LatencyMS = time.Since(start).Milliseconds()
	return result
}

func (p OpenAICompatibleProvider) generateBridge(aContexts, bContexts []domain.ContextItem) (BridgeResult, error) {
	body := chatRequest{
		Model:          p.Model,
		EnableThinking: boolPtr(false),
		Messages: []chatMessage{
			{
				Role:    "system",
				Content: "你是 Personal Context Maintenance System 的 BridgeService。只使用输入中的 safe context。输出必须是 JSON，不要 Markdown。不要暴露精确地点、具体拍摄时间、人脸身份、儿童信息、asset id 或 private context。不要使用“A/B/用户A/用户B”这类占位称呼，直接用“你们”或自然描述。",
			},
			{
				Role:    "user",
				Content: bridgePrompt(aContexts, bContexts),
			},
		},
		Temperature: 0.3,
		ResponseFormat: map[string]string{
			"type": "json_object",
		},
	}
	raw, err := json.Marshal(body)
	if err != nil {
		return BridgeResult{}, err
	}
	req, err := http.NewRequest(http.MethodPost, p.BaseURL+"/chat/completions", bytes.NewReader(raw))
	if err != nil {
		return BridgeResult{}, err
	}
	req.Header.Set("Authorization", "Bearer "+p.APIKey)
	req.Header.Set("Content-Type", "application/json")
	resp, err := p.Client.Do(req)
	if err != nil {
		return BridgeResult{}, err
	}
	defer resp.Body.Close()
	respBody, err := io.ReadAll(io.LimitReader(resp.Body, 2<<20))
	if err != nil {
		return BridgeResult{}, err
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return BridgeResult{}, fmt.Errorf("llm status %d: %s", resp.StatusCode, sanitizeResponse(respBody))
	}
	var chat chatResponse
	if err := json.Unmarshal(respBody, &chat); err != nil {
		return BridgeResult{}, err
	}
	if len(chat.Choices) == 0 {
		return BridgeResult{}, fmt.Errorf("llm returned no choices")
	}
	content := strings.TrimSpace(chat.Choices[0].Message.Content)
	content = strings.TrimPrefix(content, "```json")
	content = strings.TrimPrefix(content, "```")
	content = strings.TrimSuffix(content, "```")
	var result BridgeResult
	if err := json.Unmarshal([]byte(strings.TrimSpace(content)), &result); err != nil {
		return BridgeResult{}, err
	}
	if len(result.Icebreakers) > 3 {
		result.Icebreakers = result.Icebreakers[:3]
	}
	return result, nil
}

func (p OpenAICompatibleProvider) generateCompanionReply(userText string, contexts []domain.ContextItem) (CompanionReply, error) {
	memories := compactContextTexts(contexts, 160)
	if len(memories) > 2 {
		memories = memories[:2]
	}
	body := chatRequest{
		Model:          p.Model,
		EnableThinking: boolPtr(false),
		Messages: []chatMessage{
			{
				Role:    "system",
				Content: "你是有记忆的 AI 陪伴者。先回应用户当下的话；若用户给出指令，直接执行。只在相关时轻量引用 memory。自然、具体、简短，不说教。禁止暴露 private/blocked/精确地点/人脸身份/儿童信息/asset id。只返回聊天正文，不要 JSON，不要 Markdown。",
			},
			{
				Role:    "user",
				Content: "/no_think\n" + companionTextPrompt(userText, memories),
			},
		},
		Temperature: 0.55,
		MaxTokens:   180,
	}
	raw, err := json.Marshal(body)
	if err != nil {
		return CompanionReply{}, err
	}
	req, err := http.NewRequest(http.MethodPost, p.BaseURL+"/chat/completions", bytes.NewReader(raw))
	if err != nil {
		return CompanionReply{}, err
	}
	req.Header.Set("Authorization", "Bearer "+p.APIKey)
	req.Header.Set("Content-Type", "application/json")
	resp, err := p.Client.Do(req)
	if err != nil {
		return CompanionReply{}, err
	}
	defer resp.Body.Close()
	respBody, err := io.ReadAll(io.LimitReader(resp.Body, 2<<20))
	if err != nil {
		return CompanionReply{}, err
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return CompanionReply{}, fmt.Errorf("llm status %d: %s", resp.StatusCode, sanitizeResponse(respBody))
	}
	var chat chatResponse
	if err := json.Unmarshal(respBody, &chat); err != nil {
		return CompanionReply{}, err
	}
	if len(chat.Choices) == 0 {
		return CompanionReply{}, fmt.Errorf("llm returned no choices")
	}
	content := strings.TrimSpace(chat.Choices[0].Message.Content)
	content = strings.TrimPrefix(content, "```")
	content = strings.TrimSuffix(content, "```")
	return CompanionReply{
		Text:       strings.TrimSpace(content),
		MemoryUsed: memories,
		Suggestions: []string{
			"继续聊这个方向",
			"帮我整理下一步行动",
		},
	}, nil
}

func bridgePrompt(aContexts, bContexts []domain.ContextItem) string {
	input := map[string]any{
		"user_a": map[string]any{"safe_contexts": contextTexts(aContexts), "context_ids": contextIDs(aContexts)},
		"user_b": map[string]any{"safe_contexts": contextTexts(bContexts), "context_ids": contextIDs(bContexts)},
		"constraints": []string{
			"不要暴露精确 GPS 或具体街道",
			"不要提具体拍摄时间",
			"不要提照片中其他人物身份",
			"不要使用 private context",
			"只生成低冒犯、自然、可解释的连接理由",
			"不要使用 A/B 这样的占位称呼",
		},
		"output_schema": map[string]any{
			"connection_reason": "string",
			"icebreakers":       []string{"string", "string", "string"},
		},
	}
	raw, _ := json.Marshal(input)
	return string(raw)
}

func companionPrompt(userText string, contexts []domain.ContextItem) string {
	input := map[string]any{
		"user_message": userText,
		"safe_memory":  compactContextTexts(contexts, 160),
		"style":        "朋友式陪伴；可执行用户指令；结合最多2条相关memory；80-140字；最后问1个自然问题。",
		"safety":       "不泄露private/blocked/精确地点/人脸身份/儿童信息/asset id；不编造记忆。",
		"output_schema": map[string]any{
			"text":        "string",
			"memory_used": []string{"used memory text"},
			"suggestions": []string{"short next action", "short next action"},
		},
	}
	raw, _ := json.Marshal(input)
	return string(raw)
}

func companionTextPrompt(userText string, memories []string) string {
	input := map[string]any{
		"user_message": userText,
		"safe_memory":  memories,
		"task":         "用80-140个中文字回复。像朋友一样互动；如果用户下指令，直接执行；只在相关时自然提到memory；最后问一个自然问题。",
	}
	raw, _ := json.Marshal(input)
	return string(raw)
}

func compactContextTexts(contexts []domain.ContextItem, maxRunes int) []string {
	out := make([]string, 0, len(contexts))
	for _, ctx := range contexts {
		text := strings.Join(strings.Fields(ctx.Text), " ")
		runes := []rune(text)
		if len(runes) > maxRunes {
			text = string(runes[:maxRunes]) + "..."
		}
		out = append(out, text)
	}
	return out
}

func contextTexts(contexts []domain.ContextItem) []string {
	out := make([]string, 0, len(contexts))
	for _, ctx := range contexts {
		out = append(out, ctx.Text)
	}
	return out
}

func contextIDs(contexts []domain.ContextItem) []string {
	out := make([]string, 0, len(contexts))
	for _, ctx := range contexts {
		out = append(out, ctx.ID)
	}
	return out
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return strings.TrimSpace(value)
		}
	}
	return ""
}

func defaultEmbeddingBaseURL(chatBaseURL string) string {
	trimmed := strings.TrimRight(strings.TrimSpace(chatBaseURL), "/")
	if strings.Contains(trimmed, "coding.dashscope.aliyuncs.com") {
		return "https://dashscope.aliyuncs.com/compatible-mode/v1"
	}
	return trimmed
}

func boolPtr(value bool) *bool {
	return &value
}

func sanitizeResponse(body []byte) string {
	text := string(body)
	for _, marker := range []string{"sk-", "Bearer "} {
		if strings.Contains(text, marker) {
			return "<redacted>"
		}
	}
	if len(text) > 500 {
		return text[:500]
	}
	return text
}

type chatRequest struct {
	Model          string            `json:"model"`
	Messages       []chatMessage     `json:"messages"`
	Temperature    float64           `json:"temperature"`
	MaxTokens      int               `json:"max_tokens,omitempty"`
	EnableThinking *bool             `json:"enable_thinking,omitempty"`
	ResponseFormat map[string]string `json:"response_format,omitempty"`
}

type chatMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type chatResponse struct {
	Choices []struct {
		Message chatMessage `json:"message"`
	} `json:"choices"`
}

type embeddingRequest struct {
	Model          string   `json:"model"`
	Input          []string `json:"input"`
	Dimensions     int      `json:"dimensions,omitempty"`
	EncodingFormat string   `json:"encoding_format,omitempty"`
}

type embeddingResponse struct {
	Data []struct {
		Index     int       `json:"index"`
		Embedding []float64 `json:"embedding"`
	} `json:"data"`
}
