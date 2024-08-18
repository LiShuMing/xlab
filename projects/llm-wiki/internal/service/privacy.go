package service

import (
	"strings"
	"time"

	"github.com/LiShuMing/xlab/projects/llm-wiki/internal/domain"
)

type PrivacyGate struct{}

func (PrivacyGate) CanUseContext(ctx domain.ContextItem, actor string, purpose domain.Purpose, target *string) domain.PolicyDecision {
	if ctx.State != domain.StateActive {
		return domain.PolicyDecision{Allowed: false, Reason: "context_not_active"}
	}
	if ctx.DeletedAt != nil {
		return domain.PolicyDecision{Allowed: false, Reason: "context_deleted"}
	}
	if ctx.ExpiresAt != nil && ctx.ExpiresAt.Before(time.Now()) {
		return domain.PolicyDecision{Allowed: false, Reason: "context_expired"}
	}
	if ctx.Visibility == domain.VisibilityBlocked {
		return domain.PolicyDecision{Allowed: false, Reason: "visibility_blocked"}
	}
	if !domain.ContainsPurpose(ctx.Purpose, purpose) {
		return domain.PolicyDecision{Allowed: false, Reason: "purpose_not_allowed"}
	}
	if actor == ctx.UserID && purpose == domain.PurposeSelfMemory {
		return domain.PolicyDecision{Allowed: true, Reason: "owner_self_memory"}
	}
	if purpose == domain.PurposeMatching || purpose == domain.PurposeGeneration {
		if (ctx.Visibility == domain.VisibilityMatchOnly || ctx.Visibility == domain.VisibilityPublic) && ctx.Sensitivity <= domain.SensitivityNormal {
			return domain.PolicyDecision{Allowed: true, Reason: "allowed_for_" + string(purpose)}
		}
		return domain.PolicyDecision{Allowed: false, Reason: "not_allowed_for_" + string(purpose)}
	}
	return domain.PolicyDecision{Allowed: false, Reason: "default_deny"}
}

func RedactionCheck(text string) []string {
	forbidden := []string{"经纬度", "GPS", "具体街道", "具体拍摄时间", "asset_", "精确位置", "人脸身份", "儿童", "用户A", "用户B", " A ", " B "}
	var hits []string
	for _, term := range forbidden {
		if strings.Contains(text, term) {
			hits = append(hits, term)
		}
	}
	return hits
}
