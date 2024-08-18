package provider

import (
	"encoding/json"
	"fmt"
	"os"

	"github.com/LiShuMing/xlab/projects/llm-wiki/internal/domain"
)

// ReplayProvider records and replays provider calls.
// In record mode, delegates to inner provider and saves results to JSON.
// In replay mode, returns saved results matching by input hash.
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

// ExtractPhotoContext always delegates to inner (vision input is file, too large for tape).
func (p *ReplayProvider) ExtractPhotoContext(filename string, metadata map[string]any) PhotoExtraction {
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

func (p *ReplayProvider) GenerateCompanionReply(userText string, contexts []domain.ContextItem) CompanionReply {
	key := p.key("companion", userText+concatContextIDs(contexts))
	if p.mode == "replay" {
		if raw, ok := p.tape[key]; ok {
			var result CompanionReply
			if err := json.Unmarshal(raw, &result); err == nil {
				result.Provider = "replay"
				return result
			}
		}
	}
	result := p.inner.GenerateCompanionReply(userText, contexts)
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
		end := len(t)
		if end > 50 {
			end = 50
		}
		h += t[:end]
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
