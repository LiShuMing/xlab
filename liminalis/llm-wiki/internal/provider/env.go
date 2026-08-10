package provider

import (
	"os"
	"strings"

	"github.com/LiShuMing/xlab/liminalis/llm-wiki/internal/config"
)

func NewFromEnv(name string) Provider {
	config.LoadDotEnv("")
	if name == "" {
		name = os.Getenv("CTX_PROVIDER")
	}
	switch strings.ToLower(strings.TrimSpace(name)) {
	case "llm", "openai", "openai-compatible", "qwen", "dashscope":
		if p, ok := NewOpenAICompatibleFromEnv(); ok {
			return p
		}
	}
	return MockProvider{}
}
