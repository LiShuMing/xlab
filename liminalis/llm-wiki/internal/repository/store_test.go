package repository

import "testing"

func TestOpenWithOptionsDefaultsToFileBackend(t *testing.T) {
	repo, err := OpenWithOptions(Options{DataDir: t.TempDir()})
	if err != nil {
		t.Fatal(err)
	}
	if repo.Describe() == "" {
		t.Fatalf("expected repository description")
	}
	if err := repo.Init(); err != nil {
		t.Fatal(err)
	}
}

func TestPostgresBackendCanBeSelected(t *testing.T) {
	repo, err := OpenWithOptions(Options{
		Backend:     BackendPostgres,
		DatabaseURL: "postgres://ctx:ctx@localhost:5432/context_poc",
	})
	if err != nil {
		t.Fatal(err)
	}
	if repo.Describe() == "" {
		t.Fatalf("expected postgres repository description")
	}
}
