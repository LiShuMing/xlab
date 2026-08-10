package provider

import (
	"hash/fnv"
	"math"
	"strconv"
	"strings"

	"github.com/LiShuMing/xlab/liminalis/llm-wiki/internal/domain"
)

type PhotoExtraction struct {
	Text         string
	Topics       []string
	Sensitivity  domain.Sensitivity
	Confidence   float64
	PrivacyFlags map[string]bool
}

type MockProvider struct{}

func (MockProvider) Name() string {
	return "mock"
}

func (MockProvider) EmbedTexts(texts []string) EmbeddingResult {
	embeddings := make([][]float64, 0, len(texts))
	for _, text := range texts {
		embeddings = append(embeddings, hashEmbedding(text, 64))
	}
	return EmbeddingResult{
		Embeddings: embeddings,
		Provider:   "mock",
		Model:      "hash-embedding-v1",
	}
}

func (MockProvider) ExtractPhotoContext(filename string, metadata map[string]any) PhotoExtraction {
	lower := strings.ToLower(filename)
	topics := []string{"生活记录", "周末活动"}
	scene := "生活照片"
	confidence := 0.82
	if strings.Contains(lower, "market") || strings.Contains(lower, "night") || strings.Contains(filename, "夜市") {
		topics = []string{"夜市", "美食", "城市漫游", "周末探索"}
		scene = "城市夜市和美食场景"
	}
	if strings.Contains(lower, "coffee") || strings.Contains(filename, "咖啡") {
		topics = []string{"咖啡", "轻松聊天", "城市生活"}
		scene = "咖啡馆或轻松聊天场景"
	}
	if strings.Contains(lower, "tech") || strings.Contains(filename, "技术") {
		topics = []string{"科技", "AI infra", "技术活动"}
		scene = "技术活动或科技相关场景"
	}
	if contentType, _ := metadata["content_type"].(string); strings.Contains(contentType, "image/") && strings.Contains(lower, "screenshot") {
		topics = append(topics, "截图资料")
		scene = "截图或资料图片"
	}
	if supported, ok := metadata["decode_supported"].(bool); ok && !supported {
		confidence = 0.55
	}

	sensitivity := domain.SensitivityNormal
	flags := map[string]bool{
		"has_face":               strings.Contains(lower, "face"),
		"has_child_risk":         strings.Contains(lower, "child") || strings.Contains(filename, "儿童"),
		"has_exact_location":     metadata["exact_gps_available"] == true,
		"face_identity_used":     false,
		"exact_location_exposed": false,
	}
	if gps, ok := metadata["gps"].(map[string]any); ok {
		if exact, ok := gps["exact_available"].(bool); ok {
			flags["has_exact_location"] = exact
		}
	}
	if flags["has_child_risk"] {
		sensitivity = domain.SensitivityHighlySensitive
	}

	city := ""
	if v, ok := metadata["city"].(string); ok && v != "" {
		city = v
	}
	prefix := "用户拍摄过"
	if city != "" {
		prefix = "用户在" + city + "拍摄过"
	}
	sizeHint := ""
	if width, ok := metadata["width"]; ok {
		if height, ok := metadata["height"]; ok {
			sizeHint = "，图片尺寸约为" + anyToString(width) + "x" + anyToString(height)
		}
	}
	return PhotoExtraction{
		Text:         prefix + scene + sizeHint + "，适合围绕" + strings.Join(topics, "、") + "建立低压力的社交话题。",
		Topics:       topics,
		Sensitivity:  sensitivity,
		Confidence:   confidence,
		PrivacyFlags: flags,
	}
}

func anyToString(v any) string {
	switch x := v.(type) {
	case string:
		return x
	case int:
		return strconv.Itoa(x)
	case float64:
		return strconv.Itoa(int(x))
	default:
		return "unknown"
	}
}

func hashEmbedding(text string, dims int) []float64 {
	vector := make([]float64, dims)
	tokens := strings.FieldsFunc(strings.ToLower(text), func(r rune) bool {
		return r == ' ' || r == ',' || r == '，' || r == '。' || r == ';' || r == '；' || r == ':' || r == '：'
	})
	for _, token := range tokens {
		if token == "" {
			continue
		}
		h := fnv.New32a()
		_, _ = h.Write([]byte(token))
		idx := int(h.Sum32() % uint32(dims))
		vector[idx] += 1
	}
	var norm float64
	for _, v := range vector {
		norm += v * v
	}
	if norm == 0 {
		return vector
	}
	norm = math.Sqrt(norm)
	for i := range vector {
		vector[i] /= norm
	}
	return vector
}

func (MockProvider) GenerateBridge(aContexts, bContexts []domain.ContextItem) BridgeResult {
	topics := sharedTerms(aContexts, bContexts)
	if len(topics) == 0 {
		topics = []string{"轻松聊天", "城市生活"}
	}
	reason := "你们在" + strings.Join(topics, "、") + "这些话题上有自然交集，适合从低压力的生活话题开始连接。"
	if len(topics) == 1 && topics[0] == "上海" {
		reason = "你们都在上海，适合从城市生活、周末活动和轻松聊天开始连接。"
	}
	return BridgeResult{
		ConnectionReason: reason,
		Icebreakers: []string{
			"你最近有没有发现什么适合周末走走的地方？",
			"你更喜欢咖啡馆聊天，还是边走边聊的 citywalk？",
			"最近有什么让你觉得有意思的新话题吗？",
		},
		Provider: "mock",
		Model:    "mock-v1",
	}
}

func (MockProvider) GenerateCompanionReply(userText string, contexts []domain.ContextItem) CompanionReply {
	memories := contextTexts(contexts)
	if len(memories) > 3 {
		memories = memories[:3]
	}
	lead := "我听到了。"
	if strings.TrimSpace(userText) != "" {
		lead = "你刚刚说的这件事，我会先替你记下来。"
	}
	memoryLine := ""
	if len(memories) > 0 {
		memoryLine = "我也想起你之前提到过：" + strings.Join(memories, "；") + "。"
	}
	return CompanionReply{
		Text:       lead + memoryLine + "我会按你的话继续往前推：先把它沉淀成 memory，再帮你从里面找到可以行动的线索、可以继续聊的问题，以及可能连接到的人。如果现在只挑一个方向展开，你更想让我帮你梳理想法，还是帮你找同频的人？",
		MemoryUsed: memories,
		Suggestions: []string{
			"把今天的细节讲完整一点",
			"告诉我你想因此认识什么样的人",
			"发一张相关图片让我一起理解",
		},
		Provider: "mock",
		Model:    "mock-v1",
	}
}

func sharedTerms(aContexts, bContexts []domain.ContextItem) []string {
	seen := map[string]bool{}
	for _, a := range aContexts {
		for _, b := range bContexts {
			for _, term := range []string{"上海", "夜市", "美食", "城市漫游", "咖啡", "AI infra", "数据库", "科技", "展览", "创业", "周末", "探店"} {
				if strings.Contains(a.Text, term) && strings.Contains(b.Text, term) && !seen[term] {
					seen[term] = true
				}
			}
		}
	}
	out := make([]string, 0, len(seen))
	for term := range seen {
		out = append(out, term)
	}
	return out
}
