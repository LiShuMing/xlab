package service

import (
	"image"
	"image/color"
	"image/png"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/LiShuMing/xlab/liminalis/llm-wiki/internal/domain"
	"github.com/LiShuMing/xlab/liminalis/llm-wiki/internal/repository"
)

func newTestApp(t *testing.T) *App {
	t.Helper()
	store, err := repository.Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	if err := store.Init(); err != nil {
		t.Fatal(err)
	}
	return NewApp(store)
}

func TestPhotoProcessCreatesPendingPrivateContext(t *testing.T) {
	app := newTestApp(t)
	if _, err := app.CreateUser("kevin", "Kevin", "上海", ""); err != nil {
		t.Fatal(err)
	}
	photo := filepath.Join(t.TempDir(), "night_market.jpg")
	if err := os.WriteFile(photo, []byte("fake image"), 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := app.AddPhoto("kevin", photo, "demo", domain.VisibilityPrivate); err != nil {
		t.Fatal(err)
	}
	items, err := app.Process("kevin", 10)
	if err != nil {
		t.Fatal(err)
	}
	if len(items) != 1 {
		t.Fatalf("expected 1 context, got %d", len(items))
	}
	item := items[0]
	if item.State != domain.StatePendingReview {
		t.Fatalf("photo context state = %s, want pending_review", item.State)
	}
	if item.Visibility != domain.VisibilityPrivate {
		t.Fatalf("photo context visibility = %s, want private", item.Visibility)
	}
	if !domain.ContainsPurpose(item.Purpose, domain.PurposeSelfMemory) || domain.ContainsPurpose(item.Purpose, domain.PurposeMatching) {
		t.Fatalf("photo context should start as self_memory only, got %#v", item.Purpose)
	}
}

func TestPhotoIngestExtractsMetadataAndDedupes(t *testing.T) {
	app := newTestApp(t)
	if _, err := app.CreateUser("kevin", "Kevin", "上海", ""); err != nil {
		t.Fatal(err)
	}
	photo := filepath.Join(t.TempDir(), "night_market.png")
	if err := writeTestPNG(photo); err != nil {
		t.Fatal(err)
	}
	asset, err := app.AddPhotoWithOptions("kevin", photo, PhotoIngestOptions{
		Album:      "demo",
		City:       "上海",
		District:   "黄浦区",
		Visibility: domain.VisibilityPrivate,
	})
	if err != nil {
		t.Fatal(err)
	}
	if asset.Metadata["width"] != 2 || asset.Metadata["height"] != 3 {
		t.Fatalf("unexpected image dimensions metadata: %#v", asset.Metadata)
	}
	if asset.Metadata["content_type"] != "image/png" {
		t.Fatalf("unexpected content type: %#v", asset.Metadata["content_type"])
	}
	assetAgain, err := app.AddPhotoWithOptions("kevin", photo, PhotoIngestOptions{Album: "demo", Visibility: domain.VisibilityPrivate})
	if err != nil {
		t.Fatal(err)
	}
	if assetAgain.ID != asset.ID {
		t.Fatalf("expected duplicate ingest to return existing asset %s, got %s", asset.ID, assetAgain.ID)
	}
	items, err := app.Process("kevin", 10)
	if err != nil {
		t.Fatal(err)
	}
	if len(items) != 1 {
		t.Fatalf("expected one processed context, got %d", len(items))
	}
	if !strings.Contains(items[0].Text, "2x3") {
		t.Fatalf("expected context to include image dimensions, got %q", items[0].Text)
	}
}

func TestPhotoIngestWithProjectLismJPG(t *testing.T) {
	imagePath := filepath.Join("..", "..", "lism.jpg")
	if _, err := os.Stat(imagePath); err != nil {
		t.Skip("lism.jpg not present in project root")
	}
	app := newTestApp(t)
	if _, err := app.CreateUser("lism", "Li ShuMing", "上海", "数据库工程师"); err != nil {
		t.Fatal(err)
	}
	asset, err := app.AddPhotoWithOptions("lism", imagePath, PhotoIngestOptions{
		Album:      "real-photo",
		City:       "上海",
		District:   "浦东新区",
		Visibility: domain.VisibilityPrivate,
	})
	if err != nil {
		t.Fatal(err)
	}
	if asset.Metadata["content_type"] != "image/jpeg" {
		t.Fatalf("expected jpeg content type, got %#v", asset.Metadata["content_type"])
	}
	if asset.Metadata["width"] != 800 || asset.Metadata["height"] != 818 {
		t.Fatalf("unexpected lism.jpg dimensions: %#v", asset.Metadata)
	}
	items, err := app.Process("lism", 10)
	if err != nil {
		t.Fatal(err)
	}
	if len(items) != 1 {
		t.Fatalf("expected one context from lism.jpg, got %d", len(items))
	}
	if items[0].State != domain.StatePendingReview || items[0].Visibility != domain.VisibilityPrivate {
		t.Fatalf("photo context should start pending/private: %#v", items[0])
	}
	if !strings.Contains(items[0].Text, "800x818") {
		t.Fatalf("expected lism.jpg dimensions in context text: %q", items[0].Text)
	}
}

func TestApproveEnablesMatchingAndBridge(t *testing.T) {
	app := newTestApp(t)
	if _, err := app.CreateUser("kevin", "Kevin", "上海", "喜欢上海夜市和 AI infra"); err != nil {
		t.Fatal(err)
	}
	if _, err := app.CreateUser("amy", "Amy", "上海", "喜欢上海夜市、美食和科技展"); err != nil {
		t.Fatal(err)
	}
	results, err := app.Match("kevin", 5)
	if err != nil {
		t.Fatal(err)
	}
	if len(results) != 1 {
		t.Fatalf("expected one match, got %d", len(results))
	}
	if results[0].Score <= 0 {
		t.Fatalf("expected positive score")
	}
	bridge, err := app.Bridge("kevin", "amy")
	if err != nil {
		t.Fatal(err)
	}
	if len(bridge.ContextIDs) == 0 {
		t.Fatalf("bridge should include context ids")
	}
	modelCalls := app.Store.ModelCalls()
	if len(modelCalls) == 0 {
		t.Fatalf("expected bridge/match to record model calls")
	}
	last := modelCalls[len(modelCalls)-1]
	if last.TaskType != "bridge" || last.Provider == "" || last.Status == "" {
		t.Fatalf("bad model call log: %#v", last)
	}
}

func TestEmbeddingSemanticQueryAndMatch(t *testing.T) {
	app := newTestApp(t)
	if _, err := app.CreateUser("kevin", "Kevin", "上海", "喜欢上海夜市和 AI infra"); err != nil {
		t.Fatal(err)
	}
	if _, err := app.CreateUser("amy", "Amy", "上海", "喜欢上海夜市、美食和科技展，也关注 AI infra"); err != nil {
		t.Fatal(err)
	}
	if count, result, err := app.EmbedUserContexts("kevin"); err != nil {
		t.Fatal(err)
	} else if count == 0 || len(result.Embeddings) == 0 {
		t.Fatalf("expected embeddings, count=%d result=%#v", count, result)
	}
	if count, _, err := app.EmbedUserContexts("amy"); err != nil {
		t.Fatal(err)
	} else if count == 0 {
		t.Fatalf("expected amy embeddings")
	}
	results, _, err := app.QuerySelfSemantic("kevin", "AI infra 和周末城市生活")
	if err != nil {
		t.Fatal(err)
	}
	if len(results) == 0 {
		t.Fatalf("expected semantic query results")
	}
	matches, err := app.MatchSemantic("kevin", 5)
	if err != nil {
		t.Fatal(err)
	}
	if len(matches) == 0 || matches[0].Score <= 0 {
		t.Fatalf("expected semantic match, got %#v", matches)
	}
}

func TestDeletedContextExcludedFromBridge(t *testing.T) {
	app := newTestApp(t)
	if _, err := app.CreateUser("kevin", "Kevin", "上海", "喜欢上海夜市"); err != nil {
		t.Fatal(err)
	}
	if _, err := app.CreateUser("amy", "Amy", "上海", "喜欢上海夜市"); err != nil {
		t.Fatal(err)
	}
	users := app.Store.ListUsers()
	items := app.Store.ContextsByUser(users[0].ID)
	if len(items) == 0 {
		t.Fatal("expected profile context")
	}
	if _, err := app.DeleteContext(items[0].ID); err != nil {
		t.Fatal(err)
	}
	bridge, err := app.Bridge("kevin", "amy")
	if err != nil {
		t.Fatal(err)
	}
	for _, id := range bridge.ContextIDs {
		if id == items[0].ID {
			t.Fatalf("deleted context %s was used in bridge", id)
		}
	}
}

func writeTestPNG(path string) error {
	img := image.NewRGBA(image.Rect(0, 0, 2, 3))
	img.Set(0, 0, color.RGBA{R: 255, A: 255})
	file, err := os.Create(path)
	if err != nil {
		return err
	}
	defer file.Close()
	return png.Encode(file, img)
}
