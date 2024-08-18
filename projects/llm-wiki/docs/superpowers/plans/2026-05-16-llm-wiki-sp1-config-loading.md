# SP1 — ctx.yaml 配置加载

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 viper 加载 `ctx.yaml`，统一 flag/env/yaml 三层优先级 (flag > env > yaml > default)；CLI 与 web 共用 `internal/config` 包；删除 provider/env.go 与 postgres.go 中各自实现的 `loadDotEnv`，收口到一处。

**Architecture:** 新增 `internal/config/` 包，定义 `type Config struct` 映射 ctx.yaml 的全部 section。`Load(path string, overrides func(*Config))` 返回一次性的配置快照。CLI 与 web 的 main 调用 `config.Load()` 替代当前散落的 flag/env 读取。保留 `--data`、`--repo` 等 flag 作为最高优先 override；provider 的 API key/model 依然可从 env 读取，但读的 key 名称和优先级由 config 包统一管理。

**Tech Stack:** Go 1.25, `github.com/spf13/viper` v1.19 (需 `go get`)，无其他新依赖。

---

### Task 1: 安装 viper 依赖

**Files:**
- Modify: `go.mod` (via go get)
- Modify: `go.sum` (via go get)

- [ ] **Step 1: go get viper**

```bash
cd /Users/lism/work/xlab/projects/llm-wiki
go get github.com/spf13/viper@v1.19.0
```

- [ ] **Step 2: 验证编译通过**

```bash
go build ./...
```

Expected: exit 0, no new errors.

- [ ] **Step 3: Commit**

```bash
git add go.mod go.sum
git commit -m "deps: add spf13/viper for config loading"
```

---

### Task 2: 定义 Config struct

**Files:**
- Create: `internal/config/config.go`

- [ ] **Step 1: 定义 Config struct 和默认值函数**

```go
package config

type Config struct {
	App         AppConfig
	Database    DatabaseConfig
	AssetStore  AssetStoreConfig
	Models      ModelsConfig
	Privacy     PrivacyConfig
	Matching    MatchingConfig
	Replay      ReplayConfig
}

type AppConfig struct {
	Environment  string `mapstructure:"environment"`
	DefaultUser  string `mapstructure:"default_user"`
	ListenAddr   string `mapstructure:"listen_addr"`   // ctx-web only
}

type DatabaseConfig struct {
	Backend string `mapstructure:"backend"`
	URL     string `mapstructure:"url"`
}

type AssetStoreConfig struct {
	Type          string `mapstructure:"type"`
	Path          string `mapstructure:"path"`
	ProcessedPath string `mapstructure:"processed_path"`
}

type ModelsConfig struct {
	DefaultProvider string `mapstructure:"default_provider"`
}

type PrivacyConfig struct {
	DefaultVisibility              string `mapstructure:"default_visibility"`
	MaxSensitivityForMatching      int    `mapstructure:"max_sensitivity_for_matching"`
	ExposeExactGPS                 bool   `mapstructure:"expose_exact_gps"`
	AllowFaceIdentity              bool   `mapstructure:"allow_face_identity"`
	AllowChildContextForMatching   bool   `mapstructure:"allow_child_context_for_matching"`
	RequireReviewForPhotoContext   bool   `mapstructure:"require_review_for_photo_context"`
}

type MatchingConfig struct {
	TopKRetrieval       int `mapstructure:"top_k_retrieval"`
	TopKOutput          int `mapstructure:"top_k_output"`
	RecencyHalfLifeDays int `mapstructure:"recency_half_life_days"`
}

type ReplayConfig struct {
	GoldenPath string `mapstructure:"golden_path"`
}

func DefaultConfig() Config {
	return Config{
		App: AppConfig{
			Environment: "poc",
		},
		Database: DatabaseConfig{
			Backend: "file",
		},
		AssetStore: AssetStoreConfig{
			Type:          "local",
			Path:          "./data/assets",
			ProcessedPath: "./data/processed",
		},
		Models: ModelsConfig{
			DefaultProvider: "mock",
		},
		Privacy: PrivacyConfig{
			DefaultVisibility:            "private",
			MaxSensitivityForMatching:    1,
			RequireReviewForPhotoContext: true,
		},
		Matching: MatchingConfig{
			TopKRetrieval:       200,
			TopKOutput:          10,
			RecencyHalfLifeDays: 60,
		},
		Replay: ReplayConfig{
			GoldenPath: "./evals/golden",
		},
	}
}
```

- [ ] **Step 2: 验证编译**

```bash
go build ./...
```

- [ ] **Step 3: Commit**

```bash
git add internal/config/config.go
git commit -m "feat(config): define Config struct mapping ctx.yaml sections"
```

---

### Task 3: 实现 Load 函数

**Files:**
- Modify: `internal/config/config.go`
- Create: `internal/config/config_test.go`

- [ ] **Step 1: 写测试**

```go
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
```

- [ ] **Step 2: 运行测试，预期全部 FAIL**

```bash
go test ./internal/config/ -v
```

Expected: "undefined: Load"

- [ ] **Step 3: 实现 Load 函数**

在 `config.go` 末尾追加：

```go
import (
	"fmt"
	"os"
	"strings"

	"github.com/spf13/viper"
)

func Load(path string, overrides ...func(*Config)) (Config, error) {
	cfg := DefaultConfig()
	v := viper.New()

	// 1. Load yaml file if exists (lowest priority)
	if path != "" {
		v.SetConfigFile(path)
		if err := v.ReadInConfig(); err != nil {
			if _, ok := err.(viper.ConfigFileNotFoundError); !ok {
				return cfg, fmt.Errorf("read config %s: %w", path, err)
			}
			// Config file not found is ok — use defaults
		}
	}

	// 2. Bind env vars with CTX_ prefix (middle priority)
	v.SetEnvPrefix("CTX")
	v.SetEnvKeyReplacer(strings.NewReplacer(".", "_"))
	v.AutomaticEnv()

	// Unmarshal all bound values into cfg
	if err := v.Unmarshal(&cfg); err != nil {
		return cfg, fmt.Errorf("unmarshal config: %w", err)
	}

	// 3. Apply flag overrides (highest priority)
	for _, fn := range overrides {
		if fn != nil {
			fn(&cfg)
		}
	}

	return cfg, nil
}

// ProviderName returns the default provider from config, falling back to env.
func (c Config) ProviderName() string {
	if c.Models.DefaultProvider != "" {
		return c.Models.DefaultProvider
	}
	return os.Getenv("CTX_PROVIDER")
}

// DataDir returns the asset store path as the legacy --data equivalent.
func (c Config) DataDir() string {
	return c.AssetStore.Path
}

// RepositoryBackend returns the database backend ("file" or "postgres").
func (c Config) RepositoryBackend() string {
	return c.Database.Backend
}

// DatabaseURL returns the postgres connection URL.
func (c Config) DatabaseURL() string {
	return c.Database.URL
}
```

- [ ] **Step 4: 运行测试，预期全部 PASS**

```bash
go test ./internal/config/ -v
```

- [ ] **Step 5: Commit**

```bash
git add internal/config/config.go internal/config/config_test.go
git commit -m "feat(config): implement Load with viper (flag > env > yaml > default)"
```

---

### Task 4: 改造 CLI Runner 使用 Config

**Files:**
- Modify: `internal/cli/cli.go:36-63`
- Modify: `cmd/ctx/main.go`

- [ ] **Step 1: 给 Runner struct 加 Config 字段，新增 RunWithConfig 方法**

在 `internal/cli/cli.go` 中，`type Runner struct` 改为：

```go
type Runner struct {
	Out    io.Writer
	Err    io.Writer
	Config config.Config
}
```

在 `func (r *Runner) Run` 后新增 `RunWithConfig` (替代原来的 flag-parsing + store 打开逻辑)：

```go
func (r *Runner) RunWithConfig(args []string) error {
	if len(args) == 0 {
		r.help()
		return nil
	}

	cfg := r.Config
	// Subcommand flags still parsed per-command; global flags (--data, --repo, etc)
	// are already in cfg, but we still accept --data / --repo as overrides for
	// backward compatibility.
	global := flag.NewFlagSet("ctx", flag.ContinueOnError)
	global.SetOutput(r.Err)
	dataDir := global.String("data", cfg.DataDir(), "local data directory")
	repoBackend := global.String("repo", cfg.RepositoryBackend(), "repository backend: file or postgres")
	databaseURL := global.String("database-url", cfg.DatabaseURL(), "database URL for postgres backend")
	providerName := global.String("provider", cfg.ProviderName(), "provider: mock or llm")
	if err := global.Parse(args); err != nil {
		return err
	}
	rest := global.Args()
	if len(rest) == 0 {
		r.help()
		return nil
	}

	store, err := repository.OpenWithOptions(repository.Options{
		Backend:     repository.Backend(*repoBackend),
		DataDir:     *dataDir,
		DatabaseURL: *databaseURL,
	})
	if err != nil {
		return err
	}
	app := service.NewAppWithProvider(store, provider.NewFromEnv(*providerName))
	switch rest[0] {
	case "init":
		return r.init(store)
	case "user":
		return r.user(app, rest[1:])
	case "ingest":
		return r.ingest(app, rest[1:])
	case "intent":
		return r.intent(app, rest[1:])
	case "process":
		return r.process(app, rest[1:])
	case "embed":
		return r.embed(app, rest[1:])
	case "review":
		return r.review(app, store, rest[1:])
	case "context":
		return r.context(app, store, rest[1:])
	case "query":
		return r.query(app, rest[1:])
	case "match":
		return r.match(app, rest[1:])
	case "bridge":
		return r.bridge(app, rest[1:])
	case "privacy":
		return r.privacy(store, rest[1:])
	case "cost":
		return r.cost(store, rest[1:])
	case "asset":
		return r.asset(store, rest[1:])
	case "eval":
		return r.eval(app, store, rest[1:])
	case "demo":
		return r.demo(app, store, rest[1:])
	default:
		return fmt.Errorf("unknown command %q", rest[0])
	}
}
```

原 `Run` 方法改为向后兼容 wrapper：

```go
// Run is the backward-compatible entry point. New code should use RunWithConfig
// with a pre-loaded config.Config.
func (r *Runner) Run(args []string) error {
	if r.Config == (config.Config{}) {
		r.Config = config.DefaultConfig()
	}
	return r.RunWithConfig(args)
}
```

- [ ] **Step 2: 更新 cmd/ctx/main.go**

```go
package main

import (
	"errors"
	"flag"
	"fmt"
	"os"

	"github.com/LiShuMing/xlab/projects/llm-wiki/internal/cli"
	"github.com/LiShuMing/xlab/projects/llm-wiki/internal/config"
)

func main() {
	cfg, err := config.Load("ctx.yaml")
	if err != nil {
		// Can't log without config, fallback to stderr
		os.Stderr.WriteString("config: " + err.Error() + "\n")
		os.Exit(1)
	}
	runner := &cli.Runner{Out: os.Stdout, Err: os.Stderr, Config: cfg}
	if err := runner.RunWithConfig(os.Args[1:]); err != nil {
		if errors.Is(err, flag.ErrHelp) {
			os.Exit(0)
		}
		fmt.Fprintln(os.Stderr, "error:", err)
		os.Exit(1)
	}
}
```

原 `Execute` 函数保留向前兼容。

- [ ] **Step 3: 运行现有测试确保不破坏**

```bash
go test ./internal/cli/ -v
go test ./... -count=1
```

Expected: 全部通过。

- [ ] **Step 4: Commit**

```bash
git add internal/cli/cli.go cmd/ctx/main.go
git commit -m "feat(config): wire ctx CLI to use Config via RunWithConfig"
```

---

### Task 5: 改造 ctx-web 使用 Config

**Files:**
- Modify: `cmd/ctx-web/main.go`

- [ ] **Step 1: 重写 main.go**

```go
package main

import (
	"log"
	"net/http"
	"os"

	"github.com/LiShuMing/xlab/projects/llm-wiki/internal/config"
	"github.com/LiShuMing/xlab/projects/llm-wiki/internal/provider"
	"github.com/LiShuMing/xlab/projects/llm-wiki/internal/repository"
	"github.com/LiShuMing/xlab/projects/llm-wiki/internal/service"
	"github.com/LiShuMing/xlab/projects/llm-wiki/internal/web"
)

func main() {
	cfg, err := config.Load("ctx.yaml")
	if err != nil {
		log.Fatal("config:", err)
	}

	store, err := repository.OpenWithOptions(repository.Options{
		Backend:     repository.Backend(cfg.RepositoryBackend()),
		DataDir:     cfg.DataDir(),
		DatabaseURL: cfg.DatabaseURL(),
	})
	if err != nil {
		log.Fatal(err)
	}
	if err := store.Init(); err != nil {
		log.Fatal(err)
	}
	app := service.NewAppWithProvider(store, provider.NewFromEnv(cfg.ProviderName()))
	server := web.NewServer(app, store)

	listenAddr := cfg.App.ListenAddr
	if listenAddr == "" {
		listenAddr = "127.0.0.1:8787"
	}
	if addr := os.Getenv("CTX_WEB_ADDR"); addr != "" {
		listenAddr = addr
	}

	log.Printf("ctx-web listening on http://%s", listenAddr)
	log.Fatal(http.ListenAndServe(listenAddr, server.Routes()))
}
```

删除原来的 flag 定义行（`addr`, `dataDir`, `repoBackend`, `databaseURL`, `providerName`）。

- [ ] **Step 2: 验证编译**

```bash
go build ./cmd/ctx-web/ && echo "build ok"
```

- [ ] **Step 3: Commit**

```bash
git add cmd/ctx-web/main.go
git commit -m "feat(config): wire ctx-web to use Config"
```

---

### Task 6: 收口 loadDotEnv 到 config 包

**Files:**
- Modify: `internal/config/config.go` (追加 `LoadDotEnv`)
- Modify: `internal/provider/env.go` (删除 `LoadDotEnv`，改为调用 config)
- Modify: `internal/repository/postgres.go` (删除私有 `loadDotEnv`)

- [ ] **Step 1: 把 loadDotEnv 移入 config 包，作为 init-time 调用**

在 `config.go` 末尾追加：

```go
import (
	"bufio"
	"path/filepath"
)

// LoadDotEnv reads ~/.env (or path) and sets env vars that are not already set.
// Kept from original provider/env.go; moved here so all env loading is in one
// package.
func LoadDotEnv(path string) {
	if path == "" {
		home, err := os.UserHomeDir()
		if err != nil {
			return
		}
		path = filepath.Join(home, ".env")
	}
	file, err := os.Open(path)
	if err != nil {
		return
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") || !strings.Contains(line, "=") {
			continue
		}
		key, value, ok := strings.Cut(line, "=")
		if !ok {
			continue
		}
		key = strings.TrimSpace(key)
		value = strings.Trim(strings.TrimSpace(value), `"'`)
		if key == "" {
			continue
		}
		if _, exists := os.LookupEnv(key); !exists {
			_ = os.Setenv(key, value)
		}
	}
}
```

- [ ] **Step 2: 修改 internal/provider/env.go**

删除 `LoadDotEnv` 函数定义（第 10-43 行）。`NewFromEnv` 改为调用 `config.LoadDotEnv`：

```go
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
```

- [ ] **Step 3: 修改 internal/repository/postgres.go**

删除 `loadDotEnv` 函数（第 438-469 行）。`OpenPostgres` 中 `loadDotEnv("")` 改为 `config.LoadDotEnv("")`。添加 `config` import。

- [ ] **Step 4: 验证编译 + 测试**

```bash
go build ./...
go test ./... -count=1
```

Expected: 全部通过。

- [ ] **Step 5: Commit**

```bash
git add internal/config/config.go \
        internal/provider/env.go \
        internal/repository/postgres.go
git commit -m "refactor(config): consolidate loadDotEnv into config package"
```

---

### Task 7: 更新 ctx.yaml.example 与代码同步

**Files:**
- Modify: `ctx.yaml.example`

- [ ] **Step 1: 比对 example 与 config.go 的默认值，添加缺失字段**

在 `ctx.yaml.example` 末尾追加 `listen_addr` 字段（AppConfig 有，example 无）：

```yaml
app:
  environment: poc
  default_user: kevin
  listen_addr: 127.0.0.1:8787
```

其余字段保持不动。

- [ ] **Step 2: Commit**

```bash
git add ctx.yaml.example
git commit -m "docs(config): sync ctx.yaml.example with AppConfig.ListenAddr"
```

---

### Task 8: 全量回归验证

**Files:** (none — run-only task)

- [ ] **Step 1: 运行全部测试**

```bash
go test ./... -count=1 -v 2>&1 | tail -20
```

Expected: 全部 PASS（当前 18 个测试，SP1 新增 ~4 个）。

- [ ] **Step 2: 跑 demo flow 验证端到端无回归（file 后端）**

```bash
go run ./cmd/ctx --data $(mktemp -d) demo run 2>&1 | head -20
```

Expected: 输出 Demo data ready、== Match ==、== Bridge == 等。

- [ ] **Step 3: 跑 demo flow（postgres 后端，如果有 pg）**

```bash
go run ./cmd/ctx --data $(mktemp -d) --repo postgres demo run 2>&1 || echo "skipped (no pg)"
```

- [ ] **Step 4: 验证 ctx-web 编译**

```bash
go build ./cmd/ctx/ ./cmd/ctx-web/ && echo "both binaries build ok"
```

- [ ] **Step 5: Commit（如有遗留修改）**

```bash
git status --short
```

---

### 验收标准

1. `go test ./...` 全部通过，新增 config 包 4 个测试
2. `ctx demo run` 在 file 后端输出与 SP1 前一致
3. `ctx.yaml` 缺失时使用默认值（不报错）
4. `CTX_DATABASE_BACKEND=postgres` 环境变量覆盖 yaml 中 backend
5. `--repo file` flag 覆盖 yaml 与 env
6. `go build ./cmd/ctx/ ./cmd/ctx-web/` 通过
7. `loadDotEnv` 仅存在一处 (`internal/config/config.go`)
