package cli

import (
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/LiShuMing/xlab/liminalis/llm-wiki/internal/config"
	"github.com/LiShuMing/xlab/liminalis/llm-wiki/internal/domain"
	"github.com/LiShuMing/xlab/liminalis/llm-wiki/internal/provider"
	"github.com/LiShuMing/xlab/liminalis/llm-wiki/internal/repository"
	"github.com/LiShuMing/xlab/liminalis/llm-wiki/internal/service"
)

func Execute(args []string) int {
	runner := &Runner{Out: os.Stdout, Err: os.Stderr}
	if err := runner.Run(args); err != nil {
		if errors.Is(err, flag.ErrHelp) {
			return 0
		}
		fmt.Fprintln(runner.Err, "error:", err)
		return 1
	}
	return 0
}

type Runner struct {
	Out    io.Writer
	Err    io.Writer
	Config config.Config
}

func (r *Runner) RunWithConfig(args []string) error {
	if len(args) == 0 {
		r.help()
		return nil
	}

	cfg := r.Config
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

// Run is the backward-compatible entry point. New code should use RunWithConfig
// with a pre-loaded config.Config.
func (r *Runner) Run(args []string) error {
	var zero config.Config
	if r.Config == zero {
		r.Config = config.DefaultConfig()
	}
	return r.RunWithConfig(args)
}

func (r *Runner) init(store repository.Repository) error {
	if err := store.Init(); err != nil {
		return err
	}
	fmt.Fprintf(r.Out, "Initialized context repository %s\n", store.Describe())
	return nil
}

func (r *Runner) user(app *service.App, args []string) error {
	if len(args) == 0 {
		return fmt.Errorf("usage: ctx user create|list")
	}
	switch args[0] {
	case "create":
		fs := flag.NewFlagSet("user create", flag.ContinueOnError)
		fs.SetOutput(r.Err)
		name := fs.String("name", "", "display name")
		city := fs.String("city", "", "city")
		bio := fs.String("bio", "", "profile text")
		if err := fs.Parse(interspersed(args[1:])); err != nil {
			return err
		}
		if fs.NArg() != 1 {
			return fmt.Errorf("usage: ctx user create HANDLE --name NAME --city CITY --bio BIO")
		}
		user, err := app.CreateUser(fs.Arg(0), *name, *city, *bio)
		if err != nil {
			return err
		}
		fmt.Fprintf(r.Out, "Created user %s (%s)\n", user.Handle, user.ID)
	case "list":
		for _, user := range app.Store.ListUsers() {
			fmt.Fprintf(r.Out, "%s\t%s\t%s\t%s\n", user.Handle, user.ID, user.DisplayName, user.City)
		}
	default:
		return fmt.Errorf("unknown user command %q", args[0])
	}
	return nil
}

func (r *Runner) ingest(app *service.App, args []string) error {
	if len(args) == 0 {
		return fmt.Errorf("usage: ctx ingest photo|note")
	}
	switch args[0] {
	case "note":
		fs := flag.NewFlagSet("ingest note", flag.ContinueOnError)
		fs.SetOutput(r.Err)
		user := fs.String("user", "", "user handle")
		noteType := fs.String("type", "preference", "context type")
		text := fs.String("text", "", "note text")
		visibility := fs.String("visibility", "match_only", "visibility")
		purpose := fs.String("purpose", "self_memory,matching,generation", "comma-separated purposes")
		if err := fs.Parse(interspersed(args[1:])); err != nil {
			return err
		}
		item, err := app.AddNote(*user, *noteType, *text, domain.ParseVisibility(*visibility, domain.VisibilityMatchOnly), domain.ParsePurposes(*purpose, nil))
		if err != nil {
			return err
		}
		fmt.Fprintf(r.Out, "Created active context %s from note\n", item.ID)
	case "photo":
		fs := flag.NewFlagSet("ingest photo", flag.ContinueOnError)
		fs.SetOutput(r.Err)
		user := fs.String("user", "", "user handle")
		album := fs.String("album", "", "album")
		city := fs.String("city", "", "city-level location hint")
		district := fs.String("district", "", "district-level location hint, kept as metadata")
		visibility := fs.String("visibility", "private", "visibility")
		if err := fs.Parse(interspersed(args[1:])); err != nil {
			return err
		}
		if *user == "" || fs.NArg() == 0 {
			return fmt.Errorf("usage: ctx ingest photo FILE... --user HANDLE [--album ALBUM]")
		}
		for _, path := range fs.Args() {
			asset, err := app.AddPhotoWithOptions(*user, path, service.PhotoIngestOptions{
				Album:      *album,
				City:       *city,
				District:   *district,
				Visibility: domain.ParseVisibility(*visibility, domain.VisibilityPrivate),
			})
			if err != nil {
				return err
			}
			fmt.Fprintf(r.Out, "Imported photo asset %s from %s", asset.ID, path)
			if width, ok := asset.Metadata["width"]; ok {
				fmt.Fprintf(r.Out, " width=%v", width)
			}
			if height, ok := asset.Metadata["height"]; ok {
				fmt.Fprintf(r.Out, " height=%v", height)
			}
			if contentType, ok := asset.Metadata["content_type"]; ok {
				fmt.Fprintf(r.Out, " content_type=%v", contentType)
			}
			fmt.Fprintln(r.Out)
		}
	default:
		return fmt.Errorf("unknown ingest command %q", args[0])
	}
	return nil
}

func (r *Runner) intent(app *service.App, args []string) error {
	if len(args) == 0 || args[0] != "set" {
		return fmt.Errorf("usage: ctx intent set --user HANDLE --text TEXT --ttl 14d")
	}
	fs := flag.NewFlagSet("intent set", flag.ContinueOnError)
	fs.SetOutput(r.Err)
	user := fs.String("user", "", "user handle")
	text := fs.String("text", "", "intent text")
	ttlRaw := fs.String("ttl", "14d", "ttl, e.g. 14d or 48h")
	if err := fs.Parse(interspersed(args[1:])); err != nil {
		return err
	}
	ttl, err := parseTTL(*ttlRaw)
	if err != nil {
		return err
	}
	item, err := app.AddIntent(*user, *text, ttl)
	if err != nil {
		return err
	}
	fmt.Fprintf(r.Out, "Set intent context %s expires at %s\n", item.ID, item.ExpiresAt.Format(time.RFC3339))
	return nil
}

func (r *Runner) process(app *service.App, args []string) error {
	if len(args) == 0 {
		return fmt.Errorf("usage: ctx process run|--expire-ttl")
	}
	switch args[0] {
	case "run":
		fs := flag.NewFlagSet("process run", flag.ContinueOnError)
		fs.SetOutput(r.Err)
		user := fs.String("user", "", "user handle")
		limit := fs.Int("limit", 100, "max assets")
		if err := fs.Parse(interspersed(args[1:])); err != nil {
			return err
		}
		items, err := app.Process(*user, *limit)
		if err != nil {
			return err
		}
		for _, item := range items {
			fmt.Fprintf(r.Out, "Created pending context %s from asset %s\n", item.ID, item.SourceAssetID)
		}
		fmt.Fprintf(r.Out, "Processed %d photo assets\n", len(items))
		return nil
	case "--expire-ttl":
		count, err := app.ExpireTTL()
		if err != nil {
			return err
		}
		fmt.Fprintf(r.Out, "Expired %d contexts via TTL\n", count)
		return nil
	default:
		return fmt.Errorf("usage: ctx process run|--expire-ttl")
	}
}

func (r *Runner) embed(app *service.App, args []string) error {
	if len(args) == 0 || args[0] != "run" {
		return fmt.Errorf("usage: ctx embed run --user HANDLE")
	}
	fs := flag.NewFlagSet("embed run", flag.ContinueOnError)
	fs.SetOutput(r.Err)
	user := fs.String("user", "", "user handle")
	if err := fs.Parse(interspersed(args[1:])); err != nil {
		return err
	}
	if *user == "" {
		return fmt.Errorf("usage: ctx embed run --user HANDLE")
	}
	count, result, err := app.EmbedUserContexts(*user)
	if err != nil {
		return err
	}
	fmt.Fprintf(r.Out, "Embedded %d contexts for %s provider=%s model=%s fallback=%t latency_ms=%d\n", count, *user, result.Provider, result.Model, result.FallbackUsed, result.LatencyMS)
	if result.Error != "" {
		fmt.Fprintf(r.Out, "embedding_error: %s\n", result.Error)
	}
	return nil
}

func (r *Runner) review(app *service.App, store repository.Repository, args []string) error {
	if len(args) == 0 {
		return fmt.Errorf("usage: ctx review list|approve|reject")
	}
	switch args[0] {
	case "list":
		fs := flag.NewFlagSet("review list", flag.ContinueOnError)
		fs.SetOutput(r.Err)
		user := fs.String("user", "", "user handle")
		if err := fs.Parse(interspersed(args[1:])); err != nil {
			return err
		}
		u, err := store.UserByHandle(*user)
		if err != nil {
			return err
		}
		for _, item := range store.ContextsByUser(u.ID) {
			if item.State == domain.StatePendingReview {
				printContext(r.Out, item)
			}
		}
	case "approve":
		fs := flag.NewFlagSet("review approve", flag.ContinueOnError)
		fs.SetOutput(r.Err)
		visibility := fs.String("visibility", "match_only", "visibility")
		purpose := fs.String("purpose", "self_memory,matching,generation", "purposes")
		if err := fs.Parse(interspersed(args[1:])); err != nil {
			return err
		}
		if fs.NArg() != 1 {
			return fmt.Errorf("usage: ctx review approve CTX_ID --visibility match_only")
		}
		item, err := app.ApproveContext(fs.Arg(0), domain.ParseVisibility(*visibility, domain.VisibilityMatchOnly), domain.ParsePurposes(*purpose, nil))
		if err != nil {
			return err
		}
		fmt.Fprintf(r.Out, "Approved %s as %s\n", item.ID, item.Visibility)
	case "reject":
		fs := flag.NewFlagSet("review reject", flag.ContinueOnError)
		fs.SetOutput(r.Err)
		reason := fs.String("reason", "", "reject reason")
		if err := fs.Parse(interspersed(args[1:])); err != nil {
			return err
		}
		if fs.NArg() != 1 {
			return fmt.Errorf("usage: ctx review reject CTX_ID --reason REASON")
		}
		item, err := app.RejectContext(fs.Arg(0), *reason)
		if err != nil {
			return err
		}
		fmt.Fprintf(r.Out, "Rejected %s\n", item.ID)
	default:
		return fmt.Errorf("unknown review command %q", args[0])
	}
	return nil
}

func (r *Runner) context(app *service.App, store repository.Repository, args []string) error {
	if len(args) == 0 {
		return fmt.Errorf("usage: ctx context list|edit|delete")
	}
	switch args[0] {
	case "list":
		fs := flag.NewFlagSet("context list", flag.ContinueOnError)
		fs.SetOutput(r.Err)
		user := fs.String("user", "", "user handle")
		if err := fs.Parse(interspersed(args[1:])); err != nil {
			return err
		}
		u, err := store.UserByHandle(*user)
		if err != nil {
			return err
		}
		for _, item := range store.ContextsByUser(u.ID) {
			printContext(r.Out, item)
		}
	case "edit":
		fs := flag.NewFlagSet("context edit", flag.ContinueOnError)
		fs.SetOutput(r.Err)
		text := fs.String("text", "", "new text")
		if err := fs.Parse(interspersed(args[1:])); err != nil {
			return err
		}
		if fs.NArg() != 1 {
			return fmt.Errorf("usage: ctx context edit CTX_ID --text TEXT")
		}
		item, err := app.EditContext(fs.Arg(0), *text)
		if err != nil {
			return err
		}
		fmt.Fprintf(r.Out, "Edited %s\n", item.ID)
	case "delete":
		fs := flag.NewFlagSet("context delete", flag.ContinueOnError)
		fs.SetOutput(r.Err)
		user := fs.String("user", "", "user handle")
		if err := fs.Parse(interspersed(args[1:])); err != nil {
			return err
		}
		if fs.NArg() != 1 || *user == "" {
			return fmt.Errorf("usage: ctx context delete --user HANDLE CTX_ID")
		}
		item, err := app.DeleteContextByUser(*user, fs.Arg(0))
		if err != nil {
			return err
		}
		fmt.Fprintf(r.Out, "Deleted %s\n", item.ID)
	default:
		return fmt.Errorf("unknown context command %q", args[0])
	}
	return nil
}

func (r *Runner) query(app *service.App, args []string) error {
	if len(args) == 0 || args[0] != "self" {
		return fmt.Errorf("usage: ctx query self --user HANDLE --text QUERY")
	}
	fs := flag.NewFlagSet("query self", flag.ContinueOnError)
	fs.SetOutput(r.Err)
	user := fs.String("user", "", "user handle")
	text := fs.String("text", "", "query text")
	semantic := fs.Bool("semantic", false, "use text embeddings")
	if err := fs.Parse(interspersed(args[1:])); err != nil {
		return err
	}
	if *semantic {
		results, embedding, err := app.QuerySelfSemantic(*user, *text)
		if err != nil {
			return err
		}
		fmt.Fprintf(r.Out, "Semantic query provider=%s model=%s fallback=%t latency_ms=%d\n", embedding.Provider, embedding.Model, embedding.FallbackUsed, embedding.LatencyMS)
		for i, result := range results {
			item := result.Context
			fmt.Fprintf(r.Out, "%d. %s\n   id: %s score: %.4f confidence: %.2f visibility: %s sensitivity: %d\n", i+1, item.Text, item.ID, result.Score, item.Confidence, item.Visibility, item.Sensitivity)
		}
		return nil
	}
	items, err := app.QuerySelf(*user, *text)
	if err != nil {
		return err
	}
	for i, item := range items {
		fmt.Fprintf(r.Out, "%d. %s\n   id: %s confidence: %.2f visibility: %s sensitivity: %d\n", i+1, item.Text, item.ID, item.Confidence, item.Visibility, item.Sensitivity)
	}
	return nil
}

func (r *Runner) match(app *service.App, args []string) error {
	if len(args) == 0 || args[0] != "run" {
		return fmt.Errorf("usage: ctx match run --user HANDLE --top 5")
	}
	fs := flag.NewFlagSet("match run", flag.ContinueOnError)
	fs.SetOutput(r.Err)
	user := fs.String("user", "", "user handle")
	top := fs.Int("top", 5, "top k")
	semantic := fs.Bool("semantic", false, "use text embeddings")
	_ = fs.String("pool", "all", "candidate pool")
	if err := fs.Parse(interspersed(args[1:])); err != nil {
		return err
	}
	var results []domain.MatchResult
	var err error
	if *semantic {
		results, err = app.MatchSemantic(*user, *top)
	} else {
		results, err = app.Match(*user, *top)
	}
	if err != nil {
		return err
	}
	for i, result := range results {
		fmt.Fprintf(r.Out, "#%d %s score: %.2f\n%s\n", i+1, result.TargetHandle, result.Score, result.ConnectionReason)
		for j, ice := range result.Icebreakers {
			fmt.Fprintf(r.Out, "  %d. %s\n", j+1, ice)
		}
		fmt.Fprintf(r.Out, "contexts_used: %s\n", strings.Join(result.ContextIDs, ","))
	}
	return nil
}

func (r *Runner) bridge(app *service.App, args []string) error {
	fs := flag.NewFlagSet("bridge", flag.ContinueOnError)
	fs.SetOutput(r.Err)
	user := fs.String("user", "", "user handle")
	target := fs.String("target", "", "target handle")
	if err := fs.Parse(interspersed(args)); err != nil {
		return err
	}
	result, err := app.Bridge(*user, *target)
	if err != nil {
		return err
	}
	fmt.Fprintf(r.Out, "Bridge: %s -> %s\n\nWhy:\n%s\n\nRecommended first message:\n%q\n\ncontexts_used: %s\n", *user, *target, result.ConnectionReason, result.Icebreakers[0], strings.Join(result.ContextIDs, ","))
	fmt.Fprintln(r.Out, "\nDo not mention:\n- 精确拍摄地点\n- 照片中的其他人物\n- 具体拍摄时间\n- 未确认的情绪判断")
	return nil
}

func (r *Runner) privacy(store repository.Repository, args []string) error {
	if len(args) == 0 || args[0] != "audit" {
		return fmt.Errorf("usage: ctx privacy audit --user HANDLE")
	}
	fs := flag.NewFlagSet("privacy audit", flag.ContinueOnError)
	fs.SetOutput(r.Err)
	user := fs.String("user", "", "user handle")
	if err := fs.Parse(interspersed(args[1:])); err != nil {
		return err
	}
	u, err := store.UserByHandle(*user)
	if err != nil {
		return err
	}
	counts := map[domain.Visibility]int{}
	high := 0
	for _, item := range store.ContextsByUser(u.ID) {
		counts[item.Visibility]++
		if item.Sensitivity >= domain.SensitivitySensitive {
			high++
		}
	}
	photos := 0
	for _, asset := range store.AssetsByUser(u.ID) {
		if asset.AssetType == "photo" {
			photos++
		}
	}
	fmt.Fprintf(r.Out, "Privacy Audit for %s\n\nAssets:\n  photos: %d\n\nContexts:\n  total: %d\n  private: %d\n  match_only: %d\n  public: %d\n  friend_only: %d\n\nHigh sensitivity contexts: %d\n", *user, photos, len(store.ContextsByUser(u.ID)), counts[domain.VisibilityPrivate], counts[domain.VisibilityMatchOnly], counts[domain.VisibilityPublic], counts[domain.VisibilityFriendOnly], high)
	return nil
}

func (r *Runner) asset(store repository.Repository, args []string) error {
	if len(args) == 0 {
		return fmt.Errorf("usage: ctx asset list|delete")
	}
	switch args[0] {
	case "list":
		fs := flag.NewFlagSet("asset list", flag.ContinueOnError)
		fs.SetOutput(r.Err)
		user := fs.String("user", "", "user handle")
		if err := fs.Parse(interspersed(args[1:])); err != nil {
			return err
		}
		u, err := store.UserByHandle(*user)
		if err != nil {
			return err
		}
		for _, asset := range store.AssetsByUser(u.ID) {
			fmt.Fprintf(r.Out, "%s\t%s\t%s\t%s\n", asset.ID, asset.AssetType, asset.Visibility, asset.OriginalFilename)
		}
	case "delete":
		fs := flag.NewFlagSet("asset delete", flag.ContinueOnError)
		fs.SetOutput(r.Err)
		cascade := fs.Bool("cascade-contexts", false, "also delete contexts from this asset")
		if err := fs.Parse(interspersed(args[1:])); err != nil {
			return err
		}
		if fs.NArg() != 1 {
			return fmt.Errorf("usage: ctx asset delete [--cascade-contexts] ASSET_ID")
		}
		asset, err := store.DeleteAsset(fs.Arg(0))
		if err != nil {
			return err
		}
		fmt.Fprintf(r.Out, "Deleted asset %s (%s)\n", asset.ID, asset.OriginalFilename)
		if *cascade {
			contexts, _ := store.DeleteContextsByAssetID(asset.ID)
			for _, ctx := range contexts {
				fmt.Fprintf(r.Out, "  cascade-deleted context %s\n", ctx.ID)
			}
		}
	default:
		return fmt.Errorf("usage: ctx asset list|delete")
	}
	return nil
}

func (r *Runner) cost(store repository.Repository, args []string) error {
	if len(args) == 0 || args[0] != "show" {
		return fmt.Errorf("usage: ctx cost show")
	}
	type stat struct {
		count    int
		fallback int
		failed   int
		latency  int64
	}
	stats := map[string]*stat{}
	for _, call := range store.ModelCalls() {
		key := call.Provider + "/" + call.Model + "/" + call.TaskType
		if stats[key] == nil {
			stats[key] = &stat{}
		}
		stats[key].count++
		stats[key].latency += call.LatencyMS
		if call.Status == "fallback" {
			stats[key].fallback++
		}
		if call.Status == "failed" {
			stats[key].failed++
		}
	}
	fmt.Fprintln(r.Out, "Model Call Summary")
	if len(stats) == 0 {
		fmt.Fprintln(r.Out, "  no model calls recorded")
		return nil
	}
	for key, s := range stats {
		avg := int64(0)
		if s.count > 0 {
			avg = s.latency / int64(s.count)
		}
		fmt.Fprintf(r.Out, "  %s calls=%d fallback=%d failed=%d avg_latency_ms=%d\n", key, s.count, s.fallback, s.failed, avg)
	}
	return nil
}

func (r *Runner) eval(app *service.App, store repository.Repository, args []string) error {
	if len(args) == 0 || args[0] != "run" {
		return fmt.Errorf("usage: ctx eval run --suite privacy|deletion|all")
	}
	fs := flag.NewFlagSet("eval run", flag.ContinueOnError)
	fs.SetOutput(r.Err)
	suite := fs.String("suite", "all", "suite")
	if err := fs.Parse(interspersed(args[1:])); err != nil {
		return err
	}
	failures := 0
	if *suite == "privacy" || *suite == "all" {
		for _, item := range store.AllContexts() {
			if item.Visibility == domain.VisibilityPrivate {
				decision := app.Privacy.CanUseContext(item, item.UserID, domain.PurposeMatching, nil)
				if decision.Allowed {
					failures++
					fmt.Fprintf(r.Out, "FAIL privacy_private_context_blocked context=%s\n", item.ID)
				}
			}
		}
	}
	if *suite == "deletion" || *suite == "all" {
		for _, item := range store.AllContexts() {
			if item.State == domain.StateDeleted {
				decision := app.Privacy.CanUseContext(item, item.UserID, domain.PurposeGeneration, nil)
				if decision.Allowed {
					failures++
					fmt.Fprintf(r.Out, "FAIL deletion_deleted_context_blocked context=%s\n", item.ID)
				}
			}
		}
	}
	if *suite == "bridge-llm" {
		users := store.ListUsers()
		if len(users) < 2 {
			return fmt.Errorf("bridge-llm eval needs at least two users")
		}
		a := users[0]
		b := users[1]
		result, err := app.Bridge(a.Handle, b.Handle)
		if err != nil {
			return err
		}
		hits := service.RedactionCheck(result.ConnectionReason + " " + strings.Join(result.Icebreakers, " "))
		if len(hits) > 0 {
			return fmt.Errorf("bridge redaction failed: %s", strings.Join(hits, ","))
		}
		fmt.Fprintf(r.Out, "LLM bridge provider: %s\n", app.Provider.Name())
		fmt.Fprintf(r.Out, "connection_reason: %s\n", result.ConnectionReason)
		if v, ok := result.BridgeResult["fallback_used"].(bool); ok && v {
			return fmt.Errorf("bridge provider fell back to mock")
		}
		for i, ice := range result.Icebreakers {
			fmt.Fprintf(r.Out, "icebreaker_%d: %s\n", i+1, ice)
		}
	}
	if failures > 0 {
		return fmt.Errorf("eval failed with %d failures", failures)
	}
	fmt.Fprintf(r.Out, "Eval suite %s passed\n", *suite)
	return nil
}

func (r *Runner) demo(app *service.App, store repository.Repository, args []string) error {
	if len(args) == 0 {
		return fmt.Errorf("usage: ctx demo seed|run")
	}
	switch args[0] {
	case "seed":
		return r.demoSeed(app, store)
	case "run":
		if err := store.Init(); err != nil {
			return err
		}
		if err := r.demoSeed(app, store); err != nil {
			return err
		}
		fmt.Fprintln(r.Out, "\n== Embedding ==")
		if err := r.embed(app, []string{"run", "--user", "kevin"}); err != nil {
			return err
		}
		if err := r.embed(app, []string{"run", "--user", "amy"}); err != nil {
			return err
		}
		fmt.Fprintln(r.Out, "\n== Match ==")
		if err := r.match(app, []string{"run", "--user", "kevin", "--top", "3"}); err != nil {
			return err
		}
		fmt.Fprintln(r.Out, "\n== Semantic Match ==")
		if err := r.match(app, []string{"run", "--user", "kevin", "--top", "3", "--semantic"}); err != nil {
			return err
		}
		fmt.Fprintln(r.Out, "\n== Bridge ==")
		if err := r.bridge(app, []string{"--user", "kevin", "--target", "amy"}); err != nil {
			return err
		}
		fmt.Fprintln(r.Out, "\n== Privacy ==")
		if err := r.privacy(store, []string{"audit", "--user", "kevin"}); err != nil {
			return err
		}
		fmt.Fprintln(r.Out, "\n== Cost ==")
		return r.cost(store, []string{"show"})
	default:
		return fmt.Errorf("unknown demo command %q", args[0])
	}
}

func (r *Runner) demoSeed(app *service.App, store repository.Repository) error {
	if err := store.Init(); err != nil {
		return err
	}
	if err := ensureDemoUser(app, store, "kevin", "Kevin Li", "上海", "数据库工程师，关注 AI infra、数据库系统、咖啡、旅行和城市漫游"); err != nil {
		return err
	}
	if err := ensureDemoUser(app, store, "amy", "Amy", "上海", "喜欢探店、展览、夜市和轻户外，也对科技展、AI infra 展示和创业活动感兴趣"); err != nil {
		return err
	}
	if err := ensureDemoNote(app, store, "kevin", "preference", "最近想认识同城、对 AI infra 和数据库系统感兴趣、周末可以一起喝咖啡或 citywalk 的人"); err != nil {
		return err
	}
	if err := ensureDemoNote(app, store, "amy", "preference", "希望认识同城、喜欢展览、夜市、探店、AI infra 话题和轻松周末活动的人"); err != nil {
		return err
	}
	if err := ensureDemoNote(app, store, "kevin", "safety_fixture", "private: Kevin 的精确 GPS 和私人行程不应该进入 match 或 bridge"); err != nil {
		return err
	}
	privateCtx, err := latestContextByType(store, "kevin", "safety_fixture")
	if err == nil && privateCtx.Visibility != domain.VisibilityPrivate {
		_, err = app.ApproveContext(privateCtx.ID, domain.VisibilityPrivate, []domain.Purpose{domain.PurposeSelfMemory})
		if err != nil {
			return err
		}
	}
	fmt.Fprintln(r.Out, "Demo data ready: kevin, amy, notes, and one private safety fixture")
	return nil
}

func ensureDemoUser(app *service.App, store repository.Repository, handle, name, city, bio string) error {
	if _, err := store.UserByHandle(handle); err == nil {
		return nil
	}
	_, err := app.CreateUser(handle, name, city, bio)
	return err
}

func ensureDemoNote(app *service.App, store repository.Repository, handle, noteType, text string) error {
	user, err := store.UserByHandle(handle)
	if err != nil {
		return err
	}
	for _, item := range store.ContextsByUser(user.ID) {
		if item.Type == noteType && item.Text == text {
			return nil
		}
	}
	visibility := domain.VisibilityMatchOnly
	purposes := []domain.Purpose{domain.PurposeSelfMemory, domain.PurposeMatching, domain.PurposeGeneration}
	if noteType == "safety_fixture" {
		visibility = domain.VisibilityPrivate
		purposes = []domain.Purpose{domain.PurposeSelfMemory}
	}
	_, err = app.AddNote(handle, noteType, text, visibility, purposes)
	return err
}

func latestContextByType(store repository.Repository, handle, contextType string) (domain.ContextItem, error) {
	user, err := store.UserByHandle(handle)
	if err != nil {
		return domain.ContextItem{}, err
	}
	for _, item := range store.ContextsByUser(user.ID) {
		if item.Type == contextType {
			return item, nil
		}
	}
	return domain.ContextItem{}, fmt.Errorf("context type %q not found for user %s", contextType, handle)
}

func (r *Runner) help() {
	fmt.Fprintln(r.Out, `ctx - Personal Context Maintenance POC

Commands:
  ctx demo run
  ctx demo seed
  ctx init
  ctx user create HANDLE --name NAME --city CITY --bio BIO
  ctx user list
  ctx ingest note --user HANDLE --type preference --text TEXT
  ctx ingest photo FILE... --user HANDLE --album ALBUM
  ctx intent set --user HANDLE --text TEXT --ttl 14d
  ctx process run --user HANDLE --limit 100
  ctx process --expire-ttl
  ctx embed run --user HANDLE
  ctx review list --user HANDLE
  ctx review approve CTX_ID --visibility match_only
  ctx review reject CTX_ID --reason REASON
  ctx context list --user HANDLE
  ctx context edit CTX_ID --text TEXT
  ctx context delete --user HANDLE CTX_ID
  ctx query self --user HANDLE --text QUERY
  ctx match run --user HANDLE --top 5 [--semantic]
  ctx bridge --user HANDLE --target HANDLE
  ctx asset list --user HANDLE
  ctx asset delete [--cascade-contexts] ASSET_ID
  ctx privacy audit --user HANDLE
  ctx cost show
  ctx eval run --suite all
  ctx --provider llm eval run --suite bridge-llm`)
}

func printContext(out io.Writer, item domain.ContextItem) {
	fmt.Fprintf(out, "[%s]\nstate: %s review: %s confidence: %.2f sensitivity: %d visibility: %s\nsource: %s %s\ntext:\n%s\n\n", item.ID, item.State, item.ReviewStatus, item.Confidence, item.Sensitivity, item.Visibility, item.SourceType, item.SourceAssetID, item.Text)
}

func parseTTL(raw string) (time.Duration, error) {
	raw = strings.TrimSpace(raw)
	if strings.HasSuffix(raw, "d") {
		days, err := strconv.Atoi(strings.TrimSuffix(raw, "d"))
		if err != nil {
			return 0, err
		}
		return time.Duration(days) * 24 * time.Hour, nil
	}
	return time.ParseDuration(raw)
}

func interspersed(args []string) []string {
	var flags []string
	var positionals []string
	for i := 0; i < len(args); i++ {
		arg := args[i]
		if strings.HasPrefix(arg, "-") {
			flags = append(flags, arg)
			if i+1 < len(args) && !strings.HasPrefix(args[i+1], "-") {
				flags = append(flags, args[i+1])
				i++
			}
			continue
		}
		positionals = append(positionals, arg)
	}
	return append(flags, positionals...)
}
