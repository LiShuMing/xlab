package provider

import "github.com/LiShuMing/xlab/projects/llm-wiki/internal/domain"

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
			"has_face":               false,
			"has_child_risk":         false,
			"has_exact_location":     false,
			"face_identity_used":     false,
			"exact_location_exposed": false,
		},
	}
}

func (p *GoldenProvider) EmbedTexts(texts []string) EmbeddingResult {
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

func (p *GoldenProvider) GenerateCompanionReply(userText string, contexts []domain.ContextItem) CompanionReply {
	return CompanionReply{
		Text: "我记得你一直在关注 AI infra、数据库系统，也希望通过低压力的方式认识同城的人。你刚刚这句话很适合变成一条 memory：它不是冷冰冰的标签，而是在告诉我你最近在靠近什么。要不要继续讲讲，这件事为什么今天突然变得重要？",
		MemoryUsed: []string{
			"关注 AI infra、数据库系统",
			"希望认识同城、低压力聊天的人",
		},
		Suggestions: []string{
			"继续讲今天的触发点",
			"说说想认识的人",
			"补一张相关照片",
		},
		Provider: "golden",
		Model:    "golden-v1",
	}
}
