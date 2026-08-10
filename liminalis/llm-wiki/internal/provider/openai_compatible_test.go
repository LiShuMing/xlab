package provider

import (
	"os"
	"strings"
	"testing"

	"github.com/LiShuMing/xlab/liminalis/llm-wiki/internal/config"
	"github.com/LiShuMing/xlab/liminalis/llm-wiki/internal/domain"
)

func TestOpenAICompatibleBridgeIntegration(t *testing.T) {
	if os.Getenv("RUN_LLM_TESTS") != "1" {
		t.Skip("set RUN_LLM_TESTS=1 to run live LLM integration")
	}
	config.LoadDotEnv("")
	p, ok := NewOpenAICompatibleFromEnv()
	if !ok {
		t.Skip("LLM_API_KEY or OPENAI_API_KEY is not configured")
	}
	a := []domain.ContextItem{{
		ID:         "ctx_a",
		Text:       "常驻城市：上海。关注 AI infra、数据库系统、咖啡和城市漫游。",
		Visibility: domain.VisibilityMatchOnly,
		Purpose:    []domain.Purpose{domain.PurposeGeneration},
		State:      domain.StateActive,
	}}
	b := []domain.ContextItem{{
		ID:         "ctx_b",
		Text:       "常驻城市：上海。喜欢探店、展览、夜市和轻户外，也对科技展感兴趣。",
		Visibility: domain.VisibilityMatchOnly,
		Purpose:    []domain.Purpose{domain.PurposeGeneration},
		State:      domain.StateActive,
	}}
	result := p.GenerateBridge(a, b)
	if result.FallbackUsed {
		t.Fatalf("live LLM fell back to mock: %s", result.Error)
	}
	if strings.TrimSpace(result.ConnectionReason) == "" {
		t.Fatalf("empty connection reason")
	}
	if len(result.Icebreakers) == 0 {
		t.Fatalf("empty icebreakers")
	}
	for _, forbidden := range []string{"经纬度", "具体街道", "asset_", "人脸身份", "儿童"} {
		if strings.Contains(result.ConnectionReason, forbidden) {
			t.Fatalf("reason leaked forbidden term %q: %s", forbidden, result.ConnectionReason)
		}
	}
}

func TestOpenAICompatibleEmbeddingIntegration(t *testing.T) {
	if os.Getenv("RUN_LLM_TESTS") != "1" {
		t.Skip("set RUN_LLM_TESTS=1 to run live LLM integration")
	}
	config.LoadDotEnv("")
	p, ok := NewOpenAICompatibleFromEnv()
	if !ok {
		t.Skip("LLM_API_KEY or OPENAI_API_KEY is not configured")
	}
	result := p.EmbedTexts([]string{"AI infra database systems", "上海 周末 咖啡 城市漫游"})
	if result.FallbackUsed {
		t.Fatalf("live embedding fell back to mock: %s", result.Error)
	}
	if len(result.Embeddings) != 2 {
		t.Fatalf("expected two embeddings, got %#v", result)
	}
	if len(result.Embeddings[0]) == 0 {
		t.Fatalf("empty embedding vector")
	}
}
