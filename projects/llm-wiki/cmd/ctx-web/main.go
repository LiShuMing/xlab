package main

import (
	"flag"
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
	configPath := flag.String("config", "ctx.yaml", "config file path")
	addr := flag.String("addr", "", "listen address")
	dataDir := flag.String("data", "", "local data directory")
	repoBackend := flag.String("repo", "", "repository backend: file or postgres")
	databaseURL := flag.String("database-url", "", "database URL for postgres backend")
	providerName := flag.String("provider", "", "provider: mock or llm")
	authToken := flag.String("auth-token", "", "web auth token")
	password := flag.String("password", "", "web login password; alias for --auth-token")
	flag.Parse()

	cfg, err := config.Load(*configPath, func(c *config.Config) {
		if *addr != "" {
			c.App.ListenAddr = *addr
		}
		if *dataDir != "" {
			c.AssetStore.Path = *dataDir
		}
		if *repoBackend != "" {
			c.Database.Backend = *repoBackend
		}
		if *databaseURL != "" {
			c.Database.URL = *databaseURL
		}
		if *providerName != "" {
			c.Models.DefaultProvider = *providerName
		}
		if *password != "" {
			c.Server.AuthToken = *password
		} else if *authToken != "" {
			c.Server.AuthToken = *authToken
		}
	})
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
	token := cfg.Server.AuthToken
	if token == "" {
		token = web.GenerateToken()
		log.Printf("generated login password: %s", token)
	} else {
		log.Printf("using configured login password")
	}
	server := web.NewServer(app, store, token)

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
