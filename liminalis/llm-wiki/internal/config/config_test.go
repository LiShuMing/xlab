package config

import (
	"os"
	"path/filepath"
	"testing"
)

func TestLoadDefaultConfig(t *testing.T) {
	dir := t.TempDir()
	// No yaml file -> use defaults
	cfg, err := Load(filepath.Join(dir, "ctx.yaml"))
	if err != nil {
		t.Fatal(err)
	}
	if cfg.App.Environment != "poc" {
		t.Errorf("expected poc, got %s", cfg.App.Environment)
	}
	if cfg.Database.Backend != "file" {
		t.Errorf("expected file, got %s", cfg.Database.Backend)
	}
	if cfg.Matching.TopKRetrieval != 200 {
		t.Errorf("expected 200, got %d", cfg.Matching.TopKRetrieval)
	}
}

func TestLoadFromYAML(t *testing.T) {
	dir := t.TempDir()
	yamlContent := `
app:
  environment: test
  default_user: bob

matching:
  top_k_retrieval: 50
  top_k_output: 5
`
	yamlPath := filepath.Join(dir, "ctx.yaml")
	if err := os.WriteFile(yamlPath, []byte(yamlContent), 0o644); err != nil {
		t.Fatal(err)
	}
	cfg, err := Load(yamlPath)
	if err != nil {
		t.Fatal(err)
	}
	if cfg.App.Environment != "test" {
		t.Errorf("expected test, got %s", cfg.App.Environment)
	}
	if cfg.App.DefaultUser != "bob" {
		t.Errorf("expected bob, got %s", cfg.App.DefaultUser)
	}
	if cfg.Matching.TopKRetrieval != 50 {
		t.Errorf("expected 50, got %d", cfg.Matching.TopKRetrieval)
	}
	// Unset fields use defaults
	if cfg.Privacy.DefaultVisibility != "private" {
		t.Errorf("expected private, got %s", cfg.Privacy.DefaultVisibility)
	}
}

func TestEnvOverridesYAML(t *testing.T) {
	dir := t.TempDir()
	yamlContent := `
database:
  backend: file
  url: ""
`
	yamlPath := filepath.Join(dir, "ctx.yaml")
	if err := os.WriteFile(yamlPath, []byte(yamlContent), 0o644); err != nil {
		t.Fatal(err)
	}
	os.Setenv("CTX_DATABASE_BACKEND", "postgres")
	defer os.Unsetenv("CTX_DATABASE_BACKEND")

	cfg, err := Load(yamlPath)
	if err != nil {
		t.Fatal(err)
	}
	if cfg.Database.Backend != "postgres" {
		t.Errorf("expected postgres from env, got %s", cfg.Database.Backend)
	}
}

func TestFlagOverridesTakePrecedence(t *testing.T) {
	dir := t.TempDir()
	yamlContent := `
matching:
  top_k_retrieval: 50
`
	yamlPath := filepath.Join(dir, "ctx.yaml")
	if err := os.WriteFile(yamlPath, []byte(yamlContent), 0o644); err != nil {
		t.Fatal(err)
	}
	os.Setenv("CTX_MATCHING_TOP_K_RETRIEVAL", "100")
	defer os.Unsetenv("CTX_MATCHING_TOP_K_RETRIEVAL")

	cfg, err := Load(yamlPath, func(c *Config) {
		c.Matching.TopKRetrieval = 200 // flag override
	})
	if err != nil {
		t.Fatal(err)
	}
	// flag wins over env, env wins over yaml
	if cfg.Matching.TopKRetrieval != 200 {
		t.Errorf("expected 200 from flag, got %d", cfg.Matching.TopKRetrieval)
	}
}
