package service

import (
	"crypto/sha256"
	"fmt"
	"image"
	_ "image/gif"
	_ "image/jpeg"
	_ "image/png"
	"io"
	"math"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"github.com/LiShuMing/xlab/projects/llm-wiki/internal/domain"
	"github.com/LiShuMing/xlab/projects/llm-wiki/internal/provider"
	"github.com/LiShuMing/xlab/projects/llm-wiki/internal/repository"
)

type App struct {
	Store    repository.Repository
	Provider provider.Provider
	Privacy  PrivacyGate
}

func NewApp(store repository.Repository) *App {
	return &App{Store: store, Provider: provider.MockProvider{}, Privacy: PrivacyGate{}}
}

func NewAppWithProvider(store repository.Repository, p provider.Provider) *App {
	if p == nil {
		p = provider.MockProvider{}
	}
	return &App{Store: store, Provider: p, Privacy: PrivacyGate{}}
}

func (a *App) CreateUser(handle, name, city, bio string) (domain.User, error) {
	now := time.Now()
	user := domain.User{
		ID:          domain.NewID("user"),
		Handle:      handle,
		DisplayName: name,
		City:        city,
		ProfileText: bio,
		CreatedAt:   now,
		UpdatedAt:   now,
	}
	if err := a.Store.AddUser(user); err != nil {
		return domain.User{}, err
	}
	if strings.TrimSpace(bio) != "" || strings.TrimSpace(city) != "" {
		profileContext := strings.TrimSpace(bio)
		if strings.TrimSpace(city) != "" {
			profileContext = "常驻城市：" + strings.TrimSpace(city) + "。" + profileContext
		}
		_, err := a.AddNote(handle, "profile", profileContext, domain.VisibilityMatchOnly, []domain.Purpose{domain.PurposeSelfMemory, domain.PurposeMatching, domain.PurposeGeneration})
		if err != nil {
			return domain.User{}, err
		}
	}
	return user, nil
}

func (a *App) AddNote(handle, noteType, text string, visibility domain.Visibility, purposes []domain.Purpose) (domain.ContextItem, error) {
	user, err := a.Store.UserByHandle(handle)
	if err != nil {
		return domain.ContextItem{}, err
	}
	now := time.Now()
	asset := domain.SourceAsset{
		ID:         domain.NewID("asset"),
		UserID:     user.ID,
		AssetType:  "note",
		Text:       text,
		Metadata:   map[string]any{"note_type": noteType},
		Visibility: visibility,
		State:      "active",
		CreatedAt:  now,
	}
	if err := a.Store.AddAsset(asset); err != nil {
		return domain.ContextItem{}, err
	}
	itemType := noteType
	if itemType == "" {
		itemType = "preference"
	}
	item := domain.ContextItem{
		ID:            domain.NewID("ctx"),
		UserID:        user.ID,
		Type:          itemType,
		Text:          text,
		Attrs:         map[string]any{"source": "user_note"},
		SourceType:    "note",
		SourceAssetID: asset.ID,
		Confidence:    1.0,
		SourceTrust:   1.0,
		Sensitivity:   domain.SensitivityNormal,
		Visibility:    visibility,
		Purpose:       purposes,
		State:         domain.StateActive,
		ReviewStatus:  domain.ReviewApproved,
		CreatedAt:     now,
		UpdatedAt:     now,
	}
	if err := a.Store.AddContext(item); err != nil {
		return domain.ContextItem{}, err
	}
	return item, nil
}

func (a *App) AddIntent(handle, text string, ttl time.Duration) (domain.ContextItem, error) {
	item, err := a.AddNote(handle, "intent", text, domain.VisibilityMatchOnly, []domain.Purpose{domain.PurposeSelfMemory, domain.PurposeMatching, domain.PurposeGeneration})
	if err != nil {
		return domain.ContextItem{}, err
	}
	expires := time.Now().Add(ttl)
	ctx, err := a.Store.UpdateContext(item.ID, func(ctx *domain.ContextItem) error {
		ctx.ExpiresAt = &expires
		ctx.UpdatedAt = time.Now()
		return nil
	})
	if err != nil {
		return domain.ContextItem{}, err
	}
	return *ctx, nil
}

func (a *App) AddPhoto(handle, path, album string, visibility domain.Visibility) (domain.SourceAsset, error) {
	return a.AddPhotoWithOptions(handle, path, PhotoIngestOptions{
		Album:      album,
		Visibility: visibility,
	})
}

type PhotoIngestOptions struct {
	Album      string
	City       string
	District   string
	Visibility domain.Visibility
}

func (a *App) AddPhotoWithOptions(handle, path string, opts PhotoIngestOptions) (domain.SourceAsset, error) {
	user, err := a.Store.UserByHandle(handle)
	if err != nil {
		return domain.SourceAsset{}, err
	}
	fileInfo, err := os.Stat(path)
	if err != nil {
		return domain.SourceAsset{}, err
	}
	if fileInfo.IsDir() {
		return domain.SourceAsset{}, fmt.Errorf("photo path %q is a directory", path)
	}
	file, err := os.Open(path)
	if err != nil {
		return domain.SourceAsset{}, err
	}
	defer file.Close()
	hasher := sha256.New()
	if _, err := io.Copy(hasher, file); err != nil {
		return domain.SourceAsset{}, err
	}
	sum := fmt.Sprintf("%x", hasher.Sum(nil))
	for _, existing := range a.Store.AssetsByUser(user.ID) {
		if existing.SHA256 == sum && existing.AssetType == "photo" {
			return existing, nil
		}
	}
	now := time.Now()
	assetID := domain.NewID("asset")
	destDir := filepath.Join(a.Store.DataDirPath(), "assets", user.ID)
	if err := os.MkdirAll(destDir, 0o755); err != nil {
		return domain.SourceAsset{}, err
	}
	dest := filepath.Join(destDir, assetID+"_"+filepath.Base(path))
	if err := copyFile(path, dest); err != nil {
		return domain.SourceAsset{}, err
	}
	meta := inspectImageMetadata(path, fileInfo)
	meta["album"] = opts.Album
	if opts.City != "" {
		meta["city"] = opts.City
	}
	if opts.District != "" {
		meta["district"] = opts.District
	}
	meta["gps"] = map[string]any{
		"exact_available":        false,
		"city":                   opts.City,
		"district":               opts.District,
		"share_level":            "city",
		"exact_location_exposed": false,
	}
	asset := domain.SourceAsset{
		ID:               assetID,
		UserID:           user.ID,
		AssetType:        "photo",
		URI:              dest,
		SHA256:           sum,
		OriginalFilename: filepath.Base(path),
		Metadata:         meta,
		Visibility:       opts.Visibility,
		Sensitivity:      domain.SensitivityNormal,
		State:            "active",
		CreatedAt:        now,
	}
	return asset, a.Store.AddAsset(asset)
}

func (a *App) Process(handle string, limit int) ([]domain.ContextItem, error) {
	user, err := a.Store.UserByHandle(handle)
	if err != nil {
		return nil, err
	}
	seen := map[string]bool{}
	for _, ctx := range a.Store.AllContexts() {
		if ctx.SourceAssetID != "" {
			seen[ctx.SourceAssetID] = true
		}
	}
	var created []domain.ContextItem
	for _, asset := range a.Store.AssetsByUser(user.ID) {
		if limit > 0 && len(created) >= limit {
			break
		}
		if asset.AssetType != "photo" || seen[asset.ID] {
			continue
		}
		extraction := a.Provider.ExtractPhotoContext(asset.OriginalFilename, asset.Metadata)
		now := time.Now()
		state := domain.StatePendingReview
		visibility := domain.VisibilityPrivate
		if extraction.Sensitivity >= domain.SensitivityHighlySensitive {
			visibility = domain.VisibilityBlocked
		}
		item := domain.ContextItem{
			ID:            domain.NewID("ctx"),
			UserID:        user.ID,
			Type:          "photo_event",
			Text:          extraction.Text,
			Attrs:         map[string]any{"topics": extraction.Topics, "privacy_flags": extraction.PrivacyFlags},
			SourceType:    "photo",
			SourceAssetID: asset.ID,
			Confidence:    extraction.Confidence,
			SourceTrust:   0.75,
			Sensitivity:   extraction.Sensitivity,
			Visibility:    visibility,
			Purpose:       []domain.Purpose{domain.PurposeSelfMemory},
			State:         state,
			ReviewStatus:  domain.ReviewUnreviewed,
			ModelProvider: a.Provider.Name(),
			ModelVersion:  "poc-v1",
			PromptVersion: "photo_extract_v1",
			CreatedAt:     now,
			UpdatedAt:     now,
		}
		if err := a.Store.AddContext(item); err != nil {
			return nil, err
		}
		created = append(created, item)
	}
	return created, nil
}

func (a *App) ApproveContext(id string, visibility domain.Visibility, purposes []domain.Purpose) (*domain.ContextItem, error) {
	return a.Store.UpdateContext(id, func(ctx *domain.ContextItem) error {
		if ctx.State == domain.StateDeleted {
			return fmt.Errorf("cannot approve deleted context")
		}
		ctx.State = domain.StateActive
		ctx.ReviewStatus = domain.ReviewApproved
		ctx.Visibility = visibility
		ctx.Purpose = purposes
		ctx.UpdatedAt = time.Now()
		return nil
	})
}

func (a *App) RejectContext(id, reason string) (*domain.ContextItem, error) {
	return a.Store.UpdateContext(id, func(ctx *domain.ContextItem) error {
		if ctx.Attrs == nil {
			ctx.Attrs = map[string]any{}
		}
		ctx.State = domain.StateRejected
		ctx.ReviewStatus = domain.ReviewRejected
		ctx.Attrs["reject_reason"] = reason
		ctx.UpdatedAt = time.Now()
		return nil
	})
}

func (a *App) EditContext(id, text string) (*domain.ContextItem, error) {
	return a.Store.UpdateContext(id, func(ctx *domain.ContextItem) error {
		ctx.Text = text
		ctx.UpdatedAt = time.Now()
		return nil
	})
}

func (a *App) DeleteContext(id string) (*domain.ContextItem, error) {
	ctx, err := a.Store.ContextByID(id)
	if err != nil {
		return nil, err
	}

	// Cascade: delete vector
	_ = a.Store.DeleteContextVector(ctx.ID)

	// Cascade: delete matches referencing this context
	_ = a.Store.DeleteMatchesByContextID(ctx.ID)

	// Cascade: delete summaries referencing this context
	_ = a.Store.DeleteSummariesBySourceContextID(ctx.ID)

	// Cascade: delete extraction jobs referencing this context
	_ = a.Store.DeleteJobsByContextID(ctx.ID)

	// Mark context as deleted (audit record retained)
	return a.Store.UpdateContext(id, func(c *domain.ContextItem) error {
		now := time.Now()
		c.State = domain.StateDeleted
		c.DeletedAt = &now
		c.UpdatedAt = now
		return nil
	})
}

func (a *App) DeleteContextByUser(handle, contextID string) (*domain.ContextItem, error) {
	user, err := a.Store.UserByHandle(handle)
	if err != nil {
		return nil, fmt.Errorf("user lookup: %w", err)
	}
	ctx, err := a.Store.ContextByID(contextID)
	if err != nil {
		return nil, err
	}
	if ctx.UserID != user.ID {
		_ = a.Store.AddAudit(domain.UsageAudit{
			ID:           domain.NewID("audit"),
			ContextID:    contextID,
			UserID:       user.ID,
			UsedBy:       "delete_context_blocked",
			TargetUserID: ctx.UserID,
			Allowed:      false,
			Reason:       "ownership_mismatch",
			CreatedAt:    time.Now(),
		})
		return nil, fmt.Errorf("context %q does not belong to user %q", contextID, handle)
	}
	return a.DeleteContext(contextID)
}

func (a *App) DeleteAsset(assetID string, cascadeContexts bool) (*domain.SourceAsset, error) {
	asset, err := a.Store.DeleteAsset(assetID)
	if err != nil {
		return nil, err
	}
	if cascadeContexts {
		contexts, _ := a.Store.DeleteContextsByAssetID(assetID)
		for _, ctx := range contexts {
			a.DeleteContext(ctx.ID)
		}
	}
	return asset, nil
}

func (a *App) QuerySelf(handle, text string) ([]domain.ContextItem, error) {
	user, err := a.Store.UserByHandle(handle)
	if err != nil {
		return nil, err
	}
	var out []domain.ContextItem
	for _, ctx := range a.Store.ContextsByUser(user.ID) {
		if ctx.Visibility == domain.VisibilityBlocked || ctx.State == domain.StateDeleted || ctx.State == domain.StateRejected {
			continue
		}
		if ctx.State == domain.StateActive || ctx.State == domain.StateExpired {
			out = append(out, ctx)
		}
	}
	sort.SliceStable(out, func(i, j int) bool {
		return textScore(out[i].Text, text) > textScore(out[j].Text, text)
	})
	return out, nil
}

func (a *App) CompanionReply(handle, text string) (provider.CompanionReply, error) {
	user, err := a.Store.UserByHandle(handle)
	if err != nil {
		return provider.CompanionReply{}, err
	}
	contexts := a.safeContexts(user.ID, user.ID, domain.PurposeSelfMemory)
	currentText := strings.TrimSpace(text)
	filtered := contexts[:0]
	for _, ctx := range contexts {
		if strings.TrimSpace(ctx.Text) == currentText {
			continue
		}
		filtered = append(filtered, ctx)
	}
	contexts = filtered
	sort.SliceStable(contexts, func(i, j int) bool {
		return textScore(contexts[i].Text, text) > textScore(contexts[j].Text, text)
	})
	if len(contexts) > 5 {
		contexts = contexts[:5]
	}
	reply := a.Provider.GenerateCompanionReply(text, contexts)
	_ = a.logCompanionCall(user.ID, reply)
	if reply.Error != "" && strings.TrimSpace(reply.Text) == "" {
		return reply, fmt.Errorf("companion llm failed: %s", reply.Error)
	}
	return reply, nil
}

type SemanticContextResult struct {
	Context domain.ContextItem
	Score   float64
}

func (a *App) EmbedUserContexts(handle string) (int, provider.EmbeddingResult, error) {
	user, err := a.Store.UserByHandle(handle)
	if err != nil {
		return 0, provider.EmbeddingResult{}, err
	}
	var contexts []domain.ContextItem
	for _, ctx := range a.Store.ContextsByUser(user.ID) {
		if ctx.State != domain.StateActive || ctx.DeletedAt != nil || ctx.Visibility == domain.VisibilityBlocked {
			continue
		}
		contexts = append(contexts, ctx)
	}
	if len(contexts) == 0 {
		return 0, provider.EmbeddingResult{}, nil
	}
	texts := make([]string, 0, len(contexts))
	for _, ctx := range contexts {
		texts = append(texts, ctx.Text)
	}
	result := a.Provider.EmbedTexts(texts)
	_ = a.logEmbeddingCall(user.ID, result)
	if len(result.Embeddings) != len(contexts) {
		return 0, result, fmt.Errorf("embedding count mismatch: got %d want %d", len(result.Embeddings), len(contexts))
	}
	for i, ctx := range contexts {
		vector := domain.ContextVector{
			ID:             domain.NewID("vec"),
			ContextID:      ctx.ID,
			UserID:         ctx.UserID,
			VectorType:     "text",
			Embedding:      result.Embeddings[i],
			EmbeddingModel: result.Model,
			Visibility:     ctx.Visibility,
			Sensitivity:    ctx.Sensitivity,
			CreatedAt:      time.Now(),
		}
		if err := a.Store.AddContextVector(vector); err != nil {
			return i, result, err
		}
	}
	return len(contexts), result, nil
}

func (a *App) QuerySelfSemantic(handle, text string) ([]SemanticContextResult, provider.EmbeddingResult, error) {
	user, err := a.Store.UserByHandle(handle)
	if err != nil {
		return nil, provider.EmbeddingResult{}, err
	}
	embedding := a.Provider.EmbedTexts([]string{text})
	_ = a.logEmbeddingCall(user.ID, embedding)
	if len(embedding.Embeddings) != 1 {
		return nil, embedding, fmt.Errorf("query embedding failed")
	}
	vectorByContext := map[string]domain.ContextVector{}
	for _, vector := range a.Store.ContextVectorsByUser(user.ID) {
		vectorByContext[vector.ContextID] = vector
	}
	var results []SemanticContextResult
	for _, ctx := range a.Store.ContextsByUser(user.ID) {
		if ctx.Visibility == domain.VisibilityBlocked || ctx.State == domain.StateDeleted || ctx.State == domain.StateRejected {
			continue
		}
		if ctx.State != domain.StateActive && ctx.State != domain.StateExpired {
			continue
		}
		vector, ok := vectorByContext[ctx.ID]
		if !ok {
			continue
		}
		results = append(results, SemanticContextResult{
			Context: ctx,
			Score:   CosineSimilarity(embedding.Embeddings[0], vector.Embedding),
		})
	}
	sort.SliceStable(results, func(i, j int) bool {
		return results[i].Score > results[j].Score
	})
	return results, embedding, nil
}

func (a *App) Match(handle string, top int) ([]domain.MatchResult, error) {
	user, err := a.Store.UserByHandle(handle)
	if err != nil {
		return nil, err
	}
	var results []domain.MatchResult
	for _, target := range a.Store.ListUsers() {
		if target.ID == user.ID {
			continue
		}
		aCtx := a.safeContexts(user.ID, user.ID, domain.PurposeMatching)
		bCtx := a.safeContexts(target.ID, user.ID, domain.PurposeMatching)
		score := matchScore(aCtx, bCtx)
		if score <= 0 {
			continue
		}
		contextIDs := collectIDs(aCtx, bCtx)
		match := domain.MatchResult{
			ID:              domain.NewID("match"),
			UserID:          user.ID,
			TargetUserID:    target.ID,
			TargetHandle:    target.Handle,
			TargetName:      target.DisplayName,
			Score:           score,
			ScoreBreakdown:  map[string]any{"shared_term_score": score},
			ContextIDs:      contextIDs,
			SafeContextPack: map[string]any{"user": texts(aCtx), "target": texts(bCtx)},
			PrivacyCheck:    map[string]any{"private_context_used": false, "exact_location_exposed": false, "face_identity_used": false},
			CreatedAt:       time.Now(),
		}
		bridge := a.Provider.GenerateBridge(aCtx, bCtx)
		_ = a.logBridgeCall(user.ID, bridge)
		match.ConnectionReason = bridge.ConnectionReason
		match.Icebreakers = bridge.Icebreakers
		match.BridgeResult = bridgeMap(bridge)
		if bridge.FallbackUsed {
			match.SafeContextPack["provider_fallback"] = true
			if bridge.Error != "" {
				match.SafeContextPack["fallback_reason"] = bridge.Error
			}
		}
		if err := a.Store.AddMatch(match); err != nil {
			return nil, err
		}
		results = append(results, match)
	}
	sort.SliceStable(results, func(i, j int) bool { return results[i].Score > results[j].Score })
	if top > 0 && len(results) > top {
		results = results[:top]
	}
	return results, nil
}

func (a *App) MatchSemantic(handle string, top int) ([]domain.MatchResult, error) {
	user, err := a.Store.UserByHandle(handle)
	if err != nil {
		return nil, err
	}
	var results []domain.MatchResult
	for _, target := range a.Store.ListUsers() {
		if target.ID == user.ID {
			continue
		}
		aCtx := a.safeContexts(user.ID, user.ID, domain.PurposeMatching)
		bCtx := a.safeContexts(target.ID, user.ID, domain.PurposeMatching)
		score := semanticUserScore(a.Store.ContextVectorsByUser(user.ID), aCtx, a.Store.ContextVectorsByUser(target.ID), bCtx)
		if score <= 0 {
			continue
		}
		contextIDs := collectIDs(aCtx, bCtx)
		match := domain.MatchResult{
			ID:              domain.NewID("match"),
			UserID:          user.ID,
			TargetUserID:    target.ID,
			TargetHandle:    target.Handle,
			TargetName:      target.DisplayName,
			Score:           score,
			ScoreBreakdown:  map[string]any{"semantic_similarity": score},
			ContextIDs:      contextIDs,
			SafeContextPack: map[string]any{"user": texts(aCtx), "target": texts(bCtx)},
			PrivacyCheck:    map[string]any{"private_context_used": false, "exact_location_exposed": false, "face_identity_used": false},
			CreatedAt:       time.Now(),
		}
		bridge := a.Provider.GenerateBridge(aCtx, bCtx)
		_ = a.logBridgeCall(user.ID, bridge)
		match.ConnectionReason = bridge.ConnectionReason
		match.Icebreakers = bridge.Icebreakers
		match.BridgeResult = bridgeMap(bridge)
		if bridge.FallbackUsed {
			match.SafeContextPack["provider_fallback"] = true
			if bridge.Error != "" {
				match.SafeContextPack["fallback_reason"] = bridge.Error
			}
		}
		if err := a.Store.AddMatch(match); err != nil {
			return nil, err
		}
		results = append(results, match)
	}
	sort.SliceStable(results, func(i, j int) bool { return results[i].Score > results[j].Score })
	if top > 0 && len(results) > top {
		results = results[:top]
	}
	return results, nil
}

func (a *App) Bridge(handle, targetHandle string) (domain.MatchResult, error) {
	user, err := a.Store.UserByHandle(handle)
	if err != nil {
		return domain.MatchResult{}, err
	}
	target, err := a.Store.UserByHandle(targetHandle)
	if err != nil {
		return domain.MatchResult{}, err
	}
	aCtx := a.safeContexts(user.ID, user.ID, domain.PurposeGeneration)
	bCtx := a.safeContexts(target.ID, user.ID, domain.PurposeGeneration)
	bridge := a.Provider.GenerateBridge(aCtx, bCtx)
	_ = a.logBridgeCall(user.ID, bridge)
	hits := RedactionCheck(bridge.ConnectionReason + " " + strings.Join(bridge.Icebreakers, " "))
	result := domain.MatchResult{
		ID:               domain.NewID("bridge"),
		UserID:           user.ID,
		TargetUserID:     target.ID,
		TargetHandle:     target.Handle,
		TargetName:       target.DisplayName,
		Score:            matchScore(aCtx, bCtx),
		ContextIDs:       collectIDs(aCtx, bCtx),
		SafeContextPack:  map[string]any{"user": texts(aCtx), "target": texts(bCtx)},
		ConnectionReason: bridge.ConnectionReason,
		Icebreakers:      bridge.Icebreakers,
		BridgeResult:     bridgeMap(bridge),
		PrivacyCheck:     map[string]any{"redaction_hits": hits, "private_context_used": false, "exact_location_exposed": len(hits) > 0, "face_identity_used": false},
		CreatedAt:        time.Now(),
	}

	if bridge.FallbackUsed {
		result.SafeContextPack["provider_fallback"] = true
		if bridge.Error != "" {
			result.SafeContextPack["fallback_reason"] = bridge.Error
		}
	}
	return result, a.Store.AddMatch(result)
}

func (a *App) logBridgeCall(userID string, bridge provider.BridgeResult) error {
	status := "succeeded"
	if bridge.FallbackUsed {
		status = "fallback"
	}
	if bridge.Error != "" && !bridge.FallbackUsed {
		status = "failed"
	}
	return a.Store.AddModelCall(domain.ModelCallLog{
		ID:        domain.NewID("call"),
		UserID:    userID,
		Provider:  bridge.Provider,
		Model:     bridge.Model,
		TaskType:  "bridge",
		LatencyMS: bridge.LatencyMS,
		Status:    status,
		Error:     bridge.Error,
		CreatedAt: time.Now(),
	})
}

func (a *App) logEmbeddingCall(userID string, embedding provider.EmbeddingResult) error {
	status := "succeeded"
	if embedding.FallbackUsed {
		status = "fallback"
	}
	if embedding.Error != "" && !embedding.FallbackUsed {
		status = "failed"
	}
	return a.Store.AddModelCall(domain.ModelCallLog{
		ID:        domain.NewID("call"),
		UserID:    userID,
		Provider:  embedding.Provider,
		Model:     embedding.Model,
		TaskType:  "embedding",
		LatencyMS: embedding.LatencyMS,
		Status:    status,
		Error:     embedding.Error,
		CreatedAt: time.Now(),
	})
}

func (a *App) logCompanionCall(userID string, reply provider.CompanionReply) error {
	status := "succeeded"
	if reply.FallbackUsed {
		status = "fallback"
	}
	if reply.Error != "" && !reply.FallbackUsed {
		status = "failed"
	}
	return a.Store.AddModelCall(domain.ModelCallLog{
		ID:        domain.NewID("call"),
		UserID:    userID,
		Provider:  reply.Provider,
		Model:     reply.Model,
		TaskType:  "companion_chat",
		LatencyMS: reply.LatencyMS,
		Status:    status,
		Error:     reply.Error,
		CreatedAt: time.Now(),
	})
}

func bridgeMap(bridge provider.BridgeResult) map[string]any {
	return map[string]any{
		"connection_reason": bridge.ConnectionReason,
		"icebreakers":       bridge.Icebreakers,
		"provider":          bridge.Provider,
		"model":             bridge.Model,
		"fallback_used":     bridge.FallbackUsed,
		"latency_ms":        bridge.LatencyMS,
		"error":             bridge.Error,
	}
}

func (a *App) safeContexts(ownerID, actorID string, purpose domain.Purpose) []domain.ContextItem {
	var out []domain.ContextItem
	for _, ctx := range a.Store.ContextsByUser(ownerID) {
		decision := a.Privacy.CanUseContext(ctx, actorID, purpose, nil)
		_ = a.Store.AddAudit(domain.UsageAudit{
			ID:        domain.NewID("audit"),
			ContextID: ctx.ID,
			UserID:    ownerID,
			UsedBy:    string(purpose),
			Purpose:   purpose,
			Allowed:   decision.Allowed,
			Reason:    decision.Reason,
			CreatedAt: time.Now(),
		})
		if decision.Allowed {
			out = append(out, ctx)
		}
	}
	return out
}

func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()
	out, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer out.Close()
	_, err = io.Copy(out, in)
	return err
}

func inspectImageMetadata(path string, fileInfo os.FileInfo) map[string]any {
	meta := map[string]any{
		"original_ext":     strings.ToLower(filepath.Ext(path)),
		"size_bytes":       fileInfo.Size(),
		"decode_supported": false,
		"privacy_note":     "exact EXIF/GPS is not exposed; matching should use city-level hints only",
	}
	contentType := detectContentType(path)
	if contentType != "" {
		meta["content_type"] = contentType
	}
	file, err := os.Open(path)
	if err != nil {
		meta["decode_error"] = err.Error()
		return meta
	}
	defer file.Close()
	config, format, err := image.DecodeConfig(file)
	if err != nil {
		meta["decode_error"] = err.Error()
		return meta
	}
	meta["decode_supported"] = true
	meta["image_format"] = format
	meta["width"] = config.Width
	meta["height"] = config.Height
	if config.Width > 0 && config.Height > 0 {
		meta["aspect_ratio"] = fmt.Sprintf("%.4f", float64(config.Width)/float64(config.Height))
	}
	return meta
}

func detectContentType(path string) string {
	file, err := os.Open(path)
	if err != nil {
		return ""
	}
	defer file.Close()
	header := make([]byte, 512)
	n, err := file.Read(header)
	if err != nil && err != io.EOF {
		return ""
	}
	return http.DetectContentType(header[:n])
}

func textScore(text, query string) int {
	score := 0
	for _, term := range strings.FieldsFunc(query, func(r rune) bool {
		return r == ' ' || r == ',' || r == '，' || r == '?' || r == '？'
	}) {
		if term != "" && strings.Contains(strings.ToLower(text), strings.ToLower(term)) {
			score++
		}
	}
	return score
}

func matchScore(a, b []domain.ContextItem) float64 {
	terms := []string{"上海", "夜市", "美食", "城市漫游", "咖啡", "AI infra", "数据库", "科技", "展览", "创业", "周末", "探店"}
	score := 0.0
	for _, term := range terms {
		if contextsContain(a, term) && contextsContain(b, term) {
			score += 0.12
		}
	}
	if score > 1 {
		return 1
	}
	return score
}

func contextsContain(contexts []domain.ContextItem, term string) bool {
	for _, ctx := range contexts {
		if strings.Contains(ctx.Text, term) {
			return true
		}
	}
	return false
}

func collectIDs(groups ...[]domain.ContextItem) []string {
	var out []string
	for _, group := range groups {
		for _, ctx := range group {
			out = append(out, ctx.ID)
		}
	}
	return out
}

func texts(contexts []domain.ContextItem) []string {
	out := make([]string, 0, len(contexts))
	for _, ctx := range contexts {
		out = append(out, ctx.Text)
	}
	return out
}

func semanticUserScore(aVectors []domain.ContextVector, aContexts []domain.ContextItem, bVectors []domain.ContextVector, bContexts []domain.ContextItem) float64 {
	aAllowed := contextSet(aContexts)
	bAllowed := contextSet(bContexts)
	best := 0.0
	for _, av := range aVectors {
		if !aAllowed[av.ContextID] {
			continue
		}
		for _, bv := range bVectors {
			if !bAllowed[bv.ContextID] {
				continue
			}
			if score := CosineSimilarity(av.Embedding, bv.Embedding); score > best {
				best = score
			}
		}
	}
	return best
}

func contextSet(contexts []domain.ContextItem) map[string]bool {
	out := map[string]bool{}
	for _, ctx := range contexts {
		out[ctx.ID] = true
	}
	return out
}

func CosineSimilarity(a, b []float64) float64 {
	if len(a) == 0 || len(a) != len(b) {
		return 0
	}
	var dot, an, bn float64
	for i := range a {
		dot += a[i] * b[i]
		an += a[i] * a[i]
		bn += b[i] * b[i]
	}
	if an == 0 || bn == 0 {
		return 0
	}
	return dot / (math.Sqrt(an) * math.Sqrt(bn))
}
