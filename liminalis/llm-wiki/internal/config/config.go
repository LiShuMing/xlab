package config

import (
	"bufio"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/spf13/viper"
)

type Config struct {
	App        AppConfig
	Server     ServerConfig
	Database   DatabaseConfig
	AssetStore AssetStoreConfig
	Models     ModelsConfig
	Privacy    PrivacyConfig
	Matching   MatchingConfig
	Replay     ReplayConfig
}

type AppConfig struct {
	Environment string `mapstructure:"environment"`
	DefaultUser string `mapstructure:"default_user"`
	ListenAddr  string `mapstructure:"listen_addr"` // ctx-web only
}

type ServerConfig struct {
	AuthToken string `mapstructure:"auth_token"`
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
	DefaultVisibility            string `mapstructure:"default_visibility"`
	MaxSensitivityForMatching    int    `mapstructure:"max_sensitivity_for_matching"`
	ExposeExactGPS               bool   `mapstructure:"expose_exact_gps"`
	AllowFaceIdentity            bool   `mapstructure:"allow_face_identity"`
	AllowChildContextForMatching bool   `mapstructure:"allow_child_context_for_matching"`
	RequireReviewForPhotoContext bool   `mapstructure:"require_review_for_photo_context"`
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
		Server: ServerConfig{
			AuthToken: "",
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

func Load(path string, overrides ...func(*Config)) (Config, error) {
	cfg := DefaultConfig()
	v := viper.New()

	// 1. Load yaml file if exists (lowest priority)
	if path != "" {
		v.SetConfigFile(path)
		if err := v.ReadInConfig(); err != nil {
			if _, ok := err.(viper.ConfigFileNotFoundError); ok {
				// Config file not found via config search — use defaults
			} else if os.IsNotExist(err) {
				// File explicitly set but does not exist — use defaults
			} else {
				return cfg, fmt.Errorf("read config %s: %w", path, err)
			}
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

// LoadDotEnv reads ~/.env (or path) and sets env vars that are not already set.
// Consolidated here so all env loading is in one package.
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
