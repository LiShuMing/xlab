package provider

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
)

type visionRequest struct {
	Model          string            `json:"model"`
	Messages       []visionMessage   `json:"messages"`
	MaxTokens      int               `json:"max_tokens"`
	Temperature    float64           `json:"temperature"`
	ResponseFormat map[string]string `json:"response_format"`
}

type visionMessage struct {
	Role    string              `json:"role"`
	Content []visionContentPart `json:"content"`
}

type visionContentPart struct {
	Type     string          `json:"type"`
	Text     string          `json:"text,omitempty"`
	ImageURL *visionImageURL `json:"image_url,omitempty"`
}

type visionImageURL struct {
	URL    string `json:"url"`
	Detail string `json:"detail,omitempty"`
}

func (p OpenAICompatibleProvider) extractPhotoContext(filename string, metadata map[string]any) (PhotoExtraction, error) {
	imageData, err := os.ReadFile(filename)
	if err != nil {
		return PhotoExtraction{}, fmt.Errorf("read photo %q: %w", filename, err)
	}

	mimeType := detectMimeType(filename)
	b64 := base64.StdEncoding.EncodeToString(imageData)
	dataURL := "data:" + mimeType + ";base64," + b64

	metadataJSON, err := json.Marshal(metadata)
	if err != nil {
		metadataJSON = []byte("{}")
	}

	systemPrompt := `你是一个个人上下文提取系统。分析用户照片并提取可用于社交匹配和安全共享的上下文。

规则：
- text 字段用中文描述照片场景（1-2句），不暴露精确地点、具体时间、人脸身份
- topics 字段列出 1-5 个话题标签
- sensitivity: 0=低, 1=普通, 2=敏感, 3=高度敏感（含儿童/人脸/精确地点则至少为 2）
- confidence: 0-1 的置信度
- privacy_flags: has_face, has_child_risk, has_exact_location, face_identity_used, exact_location_exposed
- 输出纯 JSON，不要 Markdown`

	userPrompt := fmt.Sprintf("分析这张照片并提取上下文信息。\n\n照片元数据：%s\n\n输出 JSON 格式：{\"text\":\"...\", \"topics\":[\"...\"], \"sensitivity\":0, \"confidence\":0.0, \"privacy_flags\":{\"has_face\":false}}",
		string(metadataJSON))

	reqBody := visionRequest{
		Model: p.Model,
		Messages: []visionMessage{
			{
				Role: "system",
				Content: []visionContentPart{
					{Type: "text", Text: systemPrompt},
				},
			},
			{
				Role: "user",
				Content: []visionContentPart{
					{Type: "text", Text: userPrompt},
					{Type: "image_url", ImageURL: &visionImageURL{URL: dataURL}},
				},
			},
		},
		MaxTokens:   1024,
		Temperature: 0.3,
		ResponseFormat: map[string]string{
			"type": "json_object",
		},
	}

	raw, err := json.Marshal(reqBody)
	if err != nil {
		return PhotoExtraction{}, fmt.Errorf("marshal vision request: %w", err)
	}

	req, err := http.NewRequest(http.MethodPost, p.BaseURL+"/chat/completions", bytes.NewReader(raw))
	if err != nil {
		return PhotoExtraction{}, fmt.Errorf("create vision request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+p.APIKey)
	req.Header.Set("Content-Type", "application/json")

	resp, err := p.Client.Do(req)
	if err != nil {
		return PhotoExtraction{}, fmt.Errorf("vision api call: %w", err)
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(io.LimitReader(resp.Body, 4<<20))
	if err != nil {
		return PhotoExtraction{}, fmt.Errorf("read vision response: %w", err)
	}

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return PhotoExtraction{}, fmt.Errorf("vision status %d: %s", resp.StatusCode, sanitizeResponse(respBody))
	}

	var chat chatResponse
	if err := json.Unmarshal(respBody, &chat); err != nil {
		return PhotoExtraction{}, fmt.Errorf("parse vision response: %w", err)
	}

	if len(chat.Choices) == 0 {
		return PhotoExtraction{}, fmt.Errorf("vision returned no choices")
	}

	content := chat.Choices[0].Message.Content
	content = strings.TrimPrefix(content, "```json")
	content = strings.TrimPrefix(content, "```")
	content = strings.TrimSuffix(content, "```")
	content = strings.TrimSpace(content)

	var result PhotoExtraction
	if err := json.Unmarshal([]byte(content), &result); err != nil {
		preview := content
		if len(preview) > 200 {
			preview = preview[:200]
		}
		return PhotoExtraction{}, fmt.Errorf("parse photo extraction from %q: %w", preview, err)
	}

	return result, nil
}

func detectMimeType(filename string) string {
	ext := strings.ToLower(filepath.Ext(filename))
	switch ext {
	case ".jpg", ".jpeg":
		return "image/jpeg"
	case ".png":
		return "image/png"
	case ".webp":
		return "image/webp"
	default:
		return "image/jpeg"
	}
}
