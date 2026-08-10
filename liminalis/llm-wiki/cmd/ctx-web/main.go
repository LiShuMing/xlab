package main

import (
	"flag"
	"log"
	"net"
	"net/http"
	"os"
	"path/filepath"

	"github.com/LiShuMing/xlab/liminalis/llm-wiki/internal/config"
	"github.com/LiShuMing/xlab/liminalis/llm-wiki/internal/provider"
	"github.com/LiShuMing/xlab/liminalis/llm-wiki/internal/repository"
	"github.com/LiShuMing/xlab/liminalis/llm-wiki/internal/service"
	"github.com/LiShuMing/xlab/liminalis/llm-wiki/internal/web"
)

func main() {
	configPath := flag.String("config", "ctx.yaml", "config file path")
	addr := flag.String("addr", "", "listen address")
	unixSocket := flag.String("unix-socket", "", "Unix socket path; when set, no TCP port is opened")
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
	socketPath := *unixSocket
	if socket := os.Getenv("CTX_WEB_UNIX_SOCKET"); socket != "" {
		socketPath = socket
	}

	if socketPath != "" {
		if err := os.MkdirAll(filepath.Dir(socketPath), 0o755); err != nil {
			log.Fatal(err)
		}
		_ = os.Remove(socketPath)
		listener, err := net.Listen("unix", socketPath)
		if err != nil {
			log.Fatal(err)
		}
		defer func() {
			_ = listener.Close()
			_ = os.Remove(socketPath)
		}()
		log.Printf("ctx-web listening on unix socket %s", socketPath)
		log.Fatal(http.Serve(listener, server.Routes()))
	}

	log.Printf("ctx-web listening on http://%s", listenAddr)
	log.Fatal(http.ListenAndServe(listenAddr, server.Routes()))
}
