package service

import (
	"testing"
	"time"

	"github.com/LiShuMing/xlab/projects/llm-wiki/internal/domain"
)

func TestPrivacyGateBlocksPrivateMatching(t *testing.T) {
	gate := PrivacyGate{}
	ctx := domain.ContextItem{
		ID:          "ctx_private",
		UserID:      "user_a",
		State:       domain.StateActive,
		Visibility:  domain.VisibilityPrivate,
		Sensitivity: domain.SensitivityNormal,
		Purpose:     []domain.Purpose{domain.PurposeSelfMemory, domain.PurposeMatching},
	}

	decision := gate.CanUseContext(ctx, "user_b", domain.PurposeMatching, nil)
	if decision.Allowed {
		t.Fatalf("private context should not be allowed for matching")
	}
}

func TestPrivacyGateAllowsOwnerSelfMemory(t *testing.T) {
	gate := PrivacyGate{}
	ctx := domain.ContextItem{
		ID:          "ctx_private",
		UserID:      "user_a",
		State:       domain.StateActive,
		Visibility:  domain.VisibilityPrivate,
		Sensitivity: domain.SensitivityNormal,
		Purpose:     []domain.Purpose{domain.PurposeSelfMemory},
	}

	decision := gate.CanUseContext(ctx, "user_a", domain.PurposeSelfMemory, nil)
	if !decision.Allowed {
		t.Fatalf("owner self-memory should be allowed, got %s", decision.Reason)
	}
}

func TestPrivacyGateBlocksDeletedAndExpired(t *testing.T) {
	gate := PrivacyGate{}
	now := time.Now()
	past := now.Add(-time.Hour)
	for name, ctx := range map[string]domain.ContextItem{
		"deleted": {
			ID:          "ctx_deleted",
			UserID:      "user_a",
			State:       domain.StateDeleted,
			DeletedAt:   &now,
			Visibility:  domain.VisibilityMatchOnly,
			Sensitivity: domain.SensitivityNormal,
			Purpose:     []domain.Purpose{domain.PurposeGeneration},
		},
		"expired": {
			ID:          "ctx_expired",
			UserID:      "user_a",
			State:       domain.StateActive,
			ExpiresAt:   &past,
			Visibility:  domain.VisibilityMatchOnly,
			Sensitivity: domain.SensitivityNormal,
			Purpose:     []domain.Purpose{domain.PurposeGeneration},
		},
	} {
		t.Run(name, func(t *testing.T) {
			decision := gate.CanUseContext(ctx, "user_b", domain.PurposeGeneration, nil)
			if decision.Allowed {
				t.Fatalf("%s context should be blocked", name)
			}
		})
	}
}
