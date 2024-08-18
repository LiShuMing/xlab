package repository

import (
	"os"
	"testing"
	"time"

	"github.com/LiShuMing/xlab/projects/llm-wiki/internal/domain"
)

func TestPostgresRepositoryIntegration(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping postgres integration in short mode")
	}
	if os.Getenv("RUN_PSQL_TESTS") != "1" {
		t.Skip("set RUN_PSQL_TESTS=1 to run live Postgres integration")
	}
	repo, err := OpenWithOptions(Options{Backend: BackendPostgres, DataDir: t.TempDir()})
	if err != nil {
		t.Fatal(err)
	}
	if err := repo.Init(); err != nil {
		t.Fatal(err)
	}
	now := time.Now()
	handle := "psqltest_" + now.Format("20060102150405")
	user := domain.User{
		ID:          domain.NewID("user"),
		Handle:      handle,
		DisplayName: "Postgres Test",
		City:        "上海",
		ProfileText: "integration test",
		CreatedAt:   now,
		UpdatedAt:   now,
	}
	if err := repo.AddUser(user); err != nil {
		t.Fatal(err)
	}
	got, err := repo.UserByHandle(handle)
	if err != nil {
		t.Fatal(err)
	}
	if got.ID != user.ID {
		t.Fatalf("got user id %s, want %s", got.ID, user.ID)
	}
}

func TestEntityCRUD(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping postgres integration in short mode")
	}
	if os.Getenv("RUN_PSQL_TESTS") != "1" {
		t.Skip("set RUN_PSQL_TESTS=1 to run live Postgres integration")
	}
	repo, err := OpenWithOptions(Options{Backend: BackendPostgres, DataDir: t.TempDir()})
	if err != nil {
		t.Fatal(err)
	}
	if err := repo.Init(); err != nil {
		t.Fatal(err)
	}
	e := domain.Entity{EntityType: "interest", Name: "AI"}
	if err := repo.AddEntity(e); err != nil {
		t.Fatal(err)
	}
	got, err := repo.EntityByID(e.ID)
	if err != nil {
		t.Fatal(err)
	}
	if got.Name != "AI" {
		t.Errorf("expected AI, got %s", got.Name)
	}
}

func TestUserEntityEdgeUpsert(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping postgres integration in short mode")
	}
	if os.Getenv("RUN_PSQL_TESTS") != "1" {
		t.Skip("set RUN_PSQL_TESTS=1")
	}
	repo, err := OpenWithOptions(Options{Backend: BackendPostgres, DataDir: t.TempDir()})
	if err != nil {
		t.Fatal(err)
	}
	if err := repo.Init(); err != nil {
		t.Fatal(err)
	}
	edge := domain.UserEntityEdge{UserID: "u1", EntityID: "e1", Weight: 0.8, Visibility: domain.VisibilityPrivate}
	if err := repo.UpsertUserEntityEdge(edge); err != nil {
		t.Fatal(err)
	}
	edges, err := repo.UserEntityEdges("u1")
	if err != nil {
		t.Fatal(err)
	}
	if len(edges) != 1 || edges[0].Weight != 0.8 {
		t.Fatalf("unexpected edges: %+v", edges)
	}
}

func TestUserContextSummaryCRUD(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping postgres integration in short mode")
	}
	if os.Getenv("RUN_PSQL_TESTS") != "1" {
		t.Skip("set RUN_PSQL_TESTS=1")
	}
	repo, err := OpenWithOptions(Options{Backend: BackendPostgres, DataDir: t.TempDir()})
	if err != nil {
		t.Fatal(err)
	}
	if err := repo.Init(); err != nil {
		t.Fatal(err)
	}
	summary := domain.UserContextSummary{
		UserID: "u1", SummaryType: "stable", Text: "test summary",
		Visibility: domain.VisibilityPrivate, Sensitivity: domain.SensitivityNormal,
	}
	if err := repo.AddUserContextSummary(summary); err != nil {
		t.Fatal(err)
	}
	sums, err := repo.UserContextSummaries("u1")
	if err != nil {
		t.Fatal(err)
	}
	if len(sums) != 1 {
		t.Fatalf("expected 1 summary, got %d", len(sums))
	}
}

func TestExtractionJobCRUD(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping postgres integration in short mode")
	}
	if os.Getenv("RUN_PSQL_TESTS") != "1" {
		t.Skip("set RUN_PSQL_TESTS=1")
	}
	repo, err := OpenWithOptions(Options{Backend: BackendPostgres, DataDir: t.TempDir()})
	if err != nil {
		t.Fatal(err)
	}
	if err := repo.Init(); err != nil {
		t.Fatal(err)
	}
	job := domain.ExtractionJob{UserID: "u1", JobType: "vision", Status: "pending"}
	if err := repo.AddExtractionJob(job); err != nil {
		t.Fatal(err)
	}
	updated, err := repo.UpdateExtractionJob(job.ID, func(j *domain.ExtractionJob) error {
		j.Status = "succeeded"
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
	if updated.Status != "succeeded" {
		t.Errorf("expected succeeded, got %s", updated.Status)
	}
}

func TestExtractionJobsByUser(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping postgres integration in short mode")
	}
	if os.Getenv("RUN_PSQL_TESTS") != "1" {
		t.Skip("set RUN_PSQL_TESTS=1")
	}
	repo, err := OpenWithOptions(Options{Backend: BackendPostgres, DataDir: t.TempDir()})
	if err != nil {
		t.Fatal(err)
	}
	if err := repo.Init(); err != nil {
		t.Fatal(err)
	}
	jobs, err := repo.ExtractionJobsByUser("u1")
	if err != nil {
		t.Fatal(err)
	}
	if len(jobs) < 1 {
		t.Fatal("expected at least 1 job from this test's own creation")
	}
}
