# SP3 — 真实 LLM 集成 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** 实现真实 vision 抽取 + Replay/Golden Provider + fallback 标记入 match_result + prompts/ 落地。

**Architecture:** OpenAICompatibleProvider 去掉 MockProvider 嵌入，改为内部持有 mock 作为 fallback；新增 ExtractPhotoContext 调用 vision API；ReplayProvider + GoldenProvider 各自实现 Provider 接口。

**Tech Stack:** Go 1.25, OpenAI vision API (base64 image + multipart content), JSON recording.

---

### Task 1: 重构 Provider 结构 — 去掉嵌入 MockProvider

**Files:**
- Modify: `internal/provider/openai_compatible.go`

当前 `OpenAICompatibleProvider` 嵌入了 `MockProvider`，导致 ExtractPhotoContext 自动继承 mock 实现。改为显式持有 mock 作为 fallback 字段，显式实现全部 4 个方法。

- [ ] **Step 1: 改 struct 定义**

将：
```go
type OpenAICompatibleProvider struct {
	MockProvider
	BaseURL          string
	...
}
```

改为：
```go
type OpenAICompatibleProvider struct {
	mock             MockProvider
	BaseURL          string
	...
}
```

- [ ] **Step 2: ExtractPhotoContext 临时委托给 mock**

新增方法（Task 2 会替换为真实实现）：

```go
func (p OpenAICompatibleProvider) ExtractPhotoContext(filename string, metadata map[string]any) PhotoExtraction {
	return p.mock.ExtractPhotoContext(filename, metadata)
}
```

- [ ] **Step 3: EmbedTexts / GenerateBridge 的 fallback 改为 p.mock**

把所有 `p.MockProvider.EmbedTexts(...)` 改为 `p.mock.EmbedTexts(...)`，`p.MockProvider.GenerateBridge(...)` 改为 `p.mock.GenerateBridge(...)`。

- [ ] **Step 4: 验证**

```bash
go build ./...
go test ./... -count=1
```

Expected: 全部通过。

- [ ] **Step 5: Commit**

```bash
git add internal/provider/openai_compatible.go
git commit -m "refactor(provider): replace MockProvider embedding with explicit fallback field"
```

---

### Task 2: 实现 Vision ExtractPhotoContext

**Files:**
- Create: `internal/provider/vision.go`
- Modify: `internal/provider/openai_compatible.go`

- [ ] **Step 1: 创建 vision.go — base64 编码 + vision API 调用**

```go
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
	"time"

	"github.com/LiShuMing/xlab/liminalis/llm-wiki/internal/domain"
)

type visionAPIRequest struct {
	Model     string            `json:"model"`
	Messages  []chatMessage     `json:"messages"`
	MaxTokens int               `json:"max_tokens"`
	Temperature float64         `json:"temperature"`
	ResponseFormat map[string]string `json:"response_format"`
}

type visionContentPart struct {
	Type     string            `json:"type"`
	Text     string            `json:"text,omitempty"`
	ImageURL *visionImageURL   `json:"image_url,omitempty"`
}

type visionImageURL struct {
	URL    string `json:"url"`
	Detail string `json:"detail,omitempty"`
}

func (p OpenAICompatibleProvider) extractPhotoContext(filename string, metadata map[string]any) (PhotoExtraction, error) {
	imgPath := filename
	if !filepath.IsAbs(imgPath) {
		imgPath = filepath.Join(p.mock.ExtractPhotoContext(filename, metadata).Text, filename)
	}
	data, err := os.ReadFile(filename)
	if err != nil {
		return PhotoExtraction{}, fmt.Errorf("read photo %q: %w", filename, err)
	}

	mimeType := "image/jpeg"
	if ext := strings.ToLower(filepath.Ext(filename)); ext == ".png" {
		mimeType = "image/png"
	} else if ext == ".webp" {
		mimeType = "image/webp"
	}

	b64 := base64.StdEncoding.EncodeToString(data)
	imageURL := fmt.Sprintf("data:%s;base64,%s", mimeType, b64)

	metaJSON, _ := json.Marshal(metadata)
	userContent := fmt.Sprintf("分析这张照片并提取上下文信息。\n\n照片元数据：%s\n\n输出 JSON 格式：{\"text\":\"...\", \"topics\":[\"...\"], \"sensitivity\":0, \"confidence\":0.0, \"privacy_flags\":{\"has_face\":false}}", string(metaJSON))

	systemPrompt := `你是一个个人上下文提取系统。分析用户照片并提取可用于社交匹配和安全共享的上下文。

规则：
- text 字段用中文描述照片场景（1-2句），不暴露精确地点、具体时间、人脸身份
- topics 字段列出 1-5 个话题标签
- sensitivity: 0=低, 1=普通, 2=敏感, 3=高度敏感（含儿童/人脸/精确地点则至少为 2）
- confidence: 0-1 的置信度
- privacy_flags: has_face, has_child_risk, has_exact_location, face_identity_used, exact_location_exposed
- 输出纯 JSON，不要 Markdown`

	body := visionAPIRequest{
		Model: p.Model,
		Messages: []chatMessage{
			{Role: "system", Content: systemPrompt},
			{Role: "user", Content: userContent},
		},
		MaxTokens: 500,
		Temperature: 0.2,
		ResponseFormat: map[string]string{"type": "json_object"},
	}
	raw, err := json.Marshal(body)
	if err != nil {
		return PhotoExtraction{}, err
	}

	req, err := http.NewRequest(http.MethodPost, p.BaseURL+"/chat/completions", bytes.NewReader(raw))
	if err != nil {
		return PhotoExtraction{}, err
	}
	req.Header.Set("Authorization", "Bearer "+p.APIKey)
	req.Header.Set("Content-Type", "application/json")
	resp, err := p.Client.Do(req)
	if err != nil {
		return PhotoExtraction{}, err
	}
	defer resp.Body.Close()
	respBody, err := io.ReadAll(io.LimitReader(resp.Body, 4<<20))
	if err != nil {
		return PhotoExtraction{}, err
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return PhotoExtraction{}, fmt.Errorf("vision status %d: %s", resp.StatusCode, sanitizeResponse(respBody))
	}
	var chat chatResponse
	if err := json.Unmarshal(respBody, &chat); err != nil {
		return PhotoExtraction{}, err
	}
	if len(chat.Choices) == 0 {
		return PhotoExtraction{}, fmt.Errorf("vision returned no choices")
	}
	content := strings.TrimSpace(chat.Choices[0].Message.Content)
	content = strings.TrimPrefix(content, "```json")
	content = strings.TrimPrefix(content, "```")
	content = strings.TrimSuffix(content, "```")
	content = strings.TrimSpace(content)

	var pe PhotoExtraction
	if err := json.Unmarshal([]byte(content), &pe); err != nil {
		return PhotoExtraction{}, fmt.Errorf("parse vision result: %w, raw=%s", err, content[:min(len(content), 200)])
	}
	return pe, nil
}
```

Note: Remove the spurious `imgPath` line that references `p.mock.ExtractPhotoContext`. Just directly use the filename parameter.

Actually, fix the code: remove lines 53-56 (the `imgPath` computation that incorrectly calls `p.mock.ExtractPhotoContext`) and just use `filename` directly for `os.ReadFile`.

- [ ] **Step 2: 修改 openai_compatible.go — ExtractPhotoContext 调用真实 API + fallback**

替换 Task 1 中的临时委托方法为：

```go
func (p OpenAICompatibleProvider) ExtractPhotoContext(filename string, metadata map[string]any) PhotoExtraction {
	start := time.Now()
	result, err := p.extractPhotoContext(filename, metadata)
	if err != nil {
		fallback := p.mock.ExtractPhotoContext(filename, metadata)
		fallback.Confidence = 0.0 // mark as unreliable when fallback
		return fallback
	}
	return result
}
```

- [ ] **Step 3: 验证编译**

```bash
go build ./...
go test ./... -count=1
```

- [ ] **Step 4: Commit**

```bash
git add internal/provider/vision.go internal/provider/openai_compatible.go
git commit -m "feat(provider): implement real vision ExtractPhotoContext with fallback"
```

---

### Task 3: 新增 ReplayProvider

**Files:**
- Create: `internal/provider/replay.go`

```go
package provider

import (
	"encoding/json"
	"fmt"
	"os"

	"github.com/LiShuMing/xlab/liminalis/llm-wiki/internal/domain"
)

// ReplayProvider records and replays provider calls.
// In record mode, it delegates to a real provider and saves results to JSON.
// In replay mode, it returns saved results matching by input hash.
type ReplayProvider struct {
	inner    Provider
	mode     string // "record" or "replay"
	tapePath string
	tape     map[string]json.RawMessage
}

func NewReplayProvider(inner Provider, mode, tapePath string) (*ReplayProvider, error) {
	rp := &ReplayProvider{
		inner:    inner,
		mode:     mode,
		tapePath: tapePath,
		tape:     map[string]json.RawMessage{},
	}
	if mode == "replay" && tapePath != "" {
		data, err := os.ReadFile(tapePath)
		if err != nil && !os.IsNotExist(err) {
			return nil, err
		}
		if len(data) > 0 {
			if err := json.Unmarshal(data, &rp.tape); err != nil {
				return nil, fmt.Errorf("replay tape: %w", err)
			}
		}
	}
	return rp, nil
}

func (p *ReplayProvider) Name() string {
	return "replay"
}

func (p *ReplayProvider) key(kind, id string) string {
	return kind + ":" + id
}

func (p *ReplayProvider) ExtractPhotoContext(filename string, metadata map[string]any) PhotoExtraction {
	// Vision extraction not replayed — too large, delegate to inner always.
	return p.inner.ExtractPhotoContext(filename, metadata)
}

func (p *ReplayProvider) EmbedTexts(texts []string) EmbeddingResult {
	key := p.key("embed", hashTexts(texts))
	if p.mode == "replay" {
		if raw, ok := p.tape[key]; ok {
			var result EmbeddingResult
			if err := json.Unmarshal(raw, &result); err == nil {
				result.Provider = "replay"
				return result
			}
		}
	}
	result := p.inner.EmbedTexts(texts)
	if p.mode == "record" {
		if raw, err := json.Marshal(result); err == nil {
			p.tape[key] = raw
			p.saveTape()
		}
	}
	return result
}

func (p *ReplayProvider) GenerateBridge(aContexts, bContexts []domain.ContextItem) BridgeResult {
	key := p.key("bridge", concatContextIDs(append(aContexts, bContexts...)))
	if p.mode == "replay" {
		if raw, ok := p.tape[key]; ok {
			var result BridgeResult
			if err := json.Unmarshal(raw, &result); err == nil {
				result.Provider = "replay"
				return result
			}
		}
	}
	result := p.inner.GenerateBridge(aContexts, bContexts)
	if p.mode == "record" {
		if raw, err := json.Marshal(result); err == nil {
			p.tape[key] = raw
			p.saveTape()
		}
	}
	return result
}

func (p *ReplayProvider) saveTape() {
	if p.tapePath == "" {
		return
	}
	raw, err := json.MarshalIndent(p.tape, "", "  ")
	if err != nil {
		return
	}
	_ = os.WriteFile(p.tapePath, append(raw, '\n'), 0o644)
}

func hashTexts(texts []string) string {
	h := ""
	for _, t := range texts {
		h += t[:min(len(t), 50)]
	}
	return h
}

func concatContextIDs(contexts []domain.ContextItem) string {
	ids := ""
	for _, c := range contexts {
		ids += c.ID
	}
	return ids
}
```

- [ ] **Step 2: 验证编译 + 测试**

```bash
go build ./...
go test ./... -count=1
```

- [ ] **Step 3: Commit**

```bash
git add internal/provider/replay.go
git commit -m "feat(provider): add ReplayProvider for record/replay of LLM calls"
```

---

### Task 4: 新增 GoldenProvider

**Files:**
- Create: `internal/provider/golden.go`

```go
package provider

import "github.com/LiShuMing/xlab/liminalis/llm-wiki/internal/domain"

// GoldenProvider returns fixed outputs for fixed inputs, used in eval tests.
// No real API calls are made.
type GoldenProvider struct {
	PhotoExtractions map[string]PhotoExtraction
	Embeddings       map[string]EmbeddingResult
	Bridges          map[string]BridgeResult
}

func NewGoldenProvider() *GoldenProvider {
	return &GoldenProvider{
		PhotoExtractions: map[string]PhotoExtraction{},
		Embeddings:       map[string]EmbeddingResult{},
		Bridges:          map[string]BridgeResult{},
	}
}

func (p *GoldenProvider) Name() string { return "golden" }

func (p *GoldenProvider) ExtractPhotoContext(filename string, metadata map[string]any) PhotoExtraction {
	return PhotoExtraction{
		Text:        "用户在上海市中心拍摄的街景照片，适合围绕城市漫步、周末活动建立低压力的社交话题。",
		Topics:      []string{"城市漫步", "周末活动", "上海"},
		Sensitivity: domain.SensitivityNormal,
		Confidence:  0.95,
		PrivacyFlags: map[string]bool{
			"has_face": false, "has_child_risk": false,
			"has_exact_location": false, "face_identity_used": false,
			"exact_location_exposed": false,
		},
	}
}

func (p *GoldenProvider) EmbedTexts(texts []string) EmbeddingResult {
	// Return mock-like hash embeddings for deterministic eval
	mock := MockProvider{}
	result := mock.EmbedTexts(texts)
	result.Provider = "golden"
	return result
}

func (p *GoldenProvider) GenerateBridge(aContexts, bContexts []domain.ContextItem) BridgeResult {
	return BridgeResult{
		ConnectionReason: "你们在上海、周末活动、城市漫步这些话题上有自然交集，适合从低压力的生活话题开始连接。",
		Icebreakers: []string{
			"你最近有没有发现什么适合周末走走的地方？",
			"你更喜欢咖啡馆聊天，还是边走边聊的 citywalk？",
			"最近有什么让你觉得有意思的新话题吗？",
		},
		Provider: "golden",
		Model:    "golden-v1",
	}
}
```

- [ ] **Step 2: 验证编译**

```bash
go build ./...
go test ./... -count=1
```

- [ ] **Step 3: Commit**

```bash
git add internal/provider/golden.go
git commit -m "feat(provider): add GoldenProvider for deterministic eval outputs"
```

---

### Task 5: Fallback 标记入 match_result

**Files:**
- Modify: `internal/service/services.go` (found in previous grep: services.go creates match results)

当前 match_result 创建时从 BridgeResult 拿数据但不用 FallbackUsed。需要把 `provider_fallback` 写入 match_result 的 metadata/safe_context_pack。

- [ ] **Step 1: 找到 match 流中 BridgeResult.FallbackUsed 的消费点，加写入**

阅读 `internal/service/services.go` 中 match/bridge 相关代码。在 match_result 生成点，将 `result.FallbackUsed` 写入 match_result：

```go
// 在 match result 写入时：
if bridgeResult.FallbackUsed {
    if matchResult.SafeContextPack == nil {
        matchResult.SafeContextPack = map[string]any{}
    }
    matchResult.SafeContextPack["provider_fallback"] = true
    matchResult.SafeContextPack["fallback_reason"] = bridgeResult.Error
}
```

同时对 EmbeddingResult.FallbackUsed 做同样处理：

```go
// 在 embedding 写入 match_result 时：
if embeddingResult.FallbackUsed {
    if matchResult.SafeContextPack == nil {
        matchResult.SafeContextPack = map[string]any{}
    }
    matchResult.SafeContextPack["embedding_fallback"] = true
}
```

- [ ] **Step 2: 验证编译 + 测试**

```bash
go build ./...
go test ./... -count=1
```

Expected: 全部通过。

- [ ] **Step 3: Commit**

```bash
git add internal/service/services.go
git commit -m "feat(service): write provider_fallback flag into match_result"
```

---

### Task 6: prompts/ 落地

**Files:**
- Create: `prompts/extract_photo_context.md`
- Create: `prompts/bridge.md`

从 openai_compatible.go 中提取硬编码 prompt 到文件。

- [ ] **Step 1: 创建 prompts/extract_photo_context.md**

```markdown
# Extract Photo Context — System Prompt

你是一个个人上下文提取系统。分析用户照片并提取可用于社交匹配和安全共享的上下文。

规则：
- text 字段用中文描述照片场景（1-2句），不暴露精确地点、具体时间、人脸身份
- topics 字段列出 1-5 个话题标签
- sensitivity: 0=低, 1=普通, 2=敏感, 3=高度敏感（含儿童/人脸/精确地点则至少为 2）
- confidence: 0-1 的置信度
- privacy_flags: has_face, has_child_risk, has_exact_location, face_identity_used, exact_location_exposed
- 输出纯 JSON，不要 Markdown
```

- [ ] **Step 2: 创建 prompts/bridge.md**

```markdown
# Bridge — System Prompt

你是 Personal Context Maintenance System 的 BridgeService。
只使用输入中的 safe context。输出必须是 JSON，不要 Markdown。
不要暴露精确地点、具体拍摄时间、人脸身份、儿童信息、asset id 或 private context。
不要使用"A/B/用户A/用户B"这类占位称呼，直接用"你们"或自然描述。

## Output Schema

{
  "connection_reason": "string",
  "icebreakers": ["string", "string", "string"]
}

## Constraints

- 不要暴露精确 GPS 或具体街道
- 不要提具体拍摄时间
- 不要提照片中其他人物身份
- 不要使用 private context
- 只生成低冒犯、自然、可解释的连接理由
- 不要使用 A/B 这样的占位称呼
```

- [ ] **Step 3: Commit**

```bash
git add prompts/
git commit -m "feat(prompts): extract system prompts from code to prompt files"
```

---

### Task 7: 全量回归

- [ ] **Step 1: 全部测试**

```bash
go test ./... -count=1 -v 2>&1 | tail -30
```

- [ ] **Step 2: demo flow（mock 后端，无回归）**

```bash
go run ./cmd/ctx --data $(mktemp -d) demo run 2>&1 | head -10
```

- [ ] **Step 3: Build**

```bash
go build ./cmd/ctx/ ./cmd/ctx-web/ && echo "both build ok"
```

- [ ] **Step 4: 金标 provider 编译可用**

```bash
go run ./cmd/ctx --data $(mktemp -d) --provider golden demo run 2>&1 | head -10
```

---

### 验收标准

1. `go test ./...` 全部通过
2. `ctx ingest photo` 路径（mock 模式）无回归
3. `ctx --provider golden demo run` 正常工作
4. `internal/provider/golden.go` 可被 eval suite 引用
5. `prompts/` 含 extract_photo_context.md 和 bridge.md
6. OpenAICompatibleProvider 的 ExtractPhotoContext 方法非 mock 委托
