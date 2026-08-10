package cli

import (
	"bytes"
	"path/filepath"
	"strings"
	"testing"
)

func TestCLIQuickFlow(t *testing.T) {
	data := t.TempDir()
	var out bytes.Buffer
	runner := &Runner{Out: &out, Err: &out}

	commands := [][]string{
		{"--data", data, "init"},
		{"--data", data, "user", "create", "kevin", "--name", "Kevin", "--city", "上海", "--bio", "喜欢上海夜市和 AI infra"},
		{"--data", data, "user", "create", "amy", "--name", "Amy", "--city", "上海", "--bio", "喜欢上海夜市和科技展"},
		{"--data", data, "match", "run", "--user", "kevin"},
		{"--data", data, "embed", "run", "--user", "kevin"},
		{"--data", data, "embed", "run", "--user", "amy"},
		{"--data", data, "query", "self", "--user", "kevin", "--text", "AI infra", "--semantic"},
		{"--data", data, "match", "run", "--user", "kevin", "--semantic"},
		{"--data", data, "bridge", "--user", "kevin", "--target", "amy"},
		{"--data", data, "cost", "show"},
		{"--data", data, "privacy", "audit", "--user", "kevin"},
		{"--data", data, "eval", "run", "--suite", "all"},
	}
	for _, cmd := range commands {
		if err := runner.Run(cmd); err != nil {
			t.Fatalf("%s failed: %v\n%s", strings.Join(cmd, " "), err, out.String())
		}
	}
	if !strings.Contains(out.String(), "Bridge: kevin -> amy") {
		t.Fatalf("expected bridge output, got:\n%s", out.String())
	}
	if !strings.Contains(out.String(), "Model Call Summary") {
		t.Fatalf("expected cost output, got:\n%s", out.String())
	}
	if !strings.Contains(out.String(), "Semantic query") {
		t.Fatalf("expected semantic query output, got:\n%s", out.String())
	}
	if _, err := filepath.Abs(data); err != nil {
		t.Fatal(err)
	}
}

func TestCLIDemoRun(t *testing.T) {
	data := t.TempDir()
	var out bytes.Buffer
	runner := &Runner{Out: &out, Err: &out}

	if err := runner.Run([]string{"--data", data, "demo", "run"}); err != nil {
		t.Fatalf("demo run failed: %v\n%s", err, out.String())
	}
	for _, want := range []string{"Demo data ready", "== Match ==", "== Bridge ==", "== Privacy ==", "== Cost ==", "Model Call Summary"} {
		if !strings.Contains(out.String(), want) {
			t.Fatalf("demo output missing %q:\n%s", want, out.String())
		}
	}
}
