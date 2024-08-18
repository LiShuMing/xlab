package web

import (
	"embed"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"github.com/LiShuMing/xlab/projects/llm-wiki/internal/domain"
	"github.com/LiShuMing/xlab/projects/llm-wiki/internal/repository"
	"github.com/LiShuMing/xlab/projects/llm-wiki/internal/service"
)

//go:embed templates/*
var templates embed.FS

type Server struct {
	app   *service.App
	store repository.Repository
	token string
}

func NewServer(app *service.App, store repository.Repository, token string) *Server {
	return &Server{app: app, store: store, token: token}
}

func (s *Server) Routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/", s.index)
	mux.HandleFunc("/api/", s.apiIndex)
	mux.HandleFunc("/api/auth", s.auth)
	mux.HandleFunc("/api/session", s.authMiddleware(s.session))
	mux.HandleFunc("/api/state", s.authMiddleware(s.state))
	mux.HandleFunc("/api/csrf", s.csrfHandler)
	mux.HandleFunc("/api/demo/seed", s.authMiddleware(s.csrfMiddleware(s.demoSeed)))
	mux.HandleFunc("/api/process", s.authMiddleware(s.csrfMiddleware(s.process)))
	mux.HandleFunc("/api/embed", s.authMiddleware(s.csrfMiddleware(s.embed)))
	mux.HandleFunc("/api/match", s.authMiddleware(s.csrfMiddleware(s.match)))
	mux.HandleFunc("/api/bridge", s.authMiddleware(s.csrfMiddleware(s.bridge)))
	mux.HandleFunc("/api/chat", s.authMiddleware(s.csrfMiddleware(s.chat)))
	mux.HandleFunc("/api/note", s.authMiddleware(s.csrfMiddleware(s.addNote)))
	mux.HandleFunc("/api/photo", s.authMiddleware(s.csrfMiddleware(s.addPhoto)))
	mux.HandleFunc("/api/asset/file", s.authMiddleware(s.assetFile))
	mux.HandleFunc("/api/context/edit", s.authMiddleware(s.csrfMiddleware(s.editContext)))
	mux.HandleFunc("/api/review/approve", s.authMiddleware(s.csrfMiddleware(s.approve)))
	mux.HandleFunc("/api/context/reject", s.authMiddleware(s.csrfMiddleware(s.rejectContext)))
	mux.HandleFunc("/api/context/delete", s.authMiddleware(s.csrfMiddleware(s.deleteContext)))
	mux.HandleFunc("/api/asset/delete", s.authMiddleware(s.csrfMiddleware(s.deleteAsset)))
	mux.HandleFunc("/api/intent", s.authMiddleware(s.csrfMiddleware(s.addIntent)))
	mux.HandleFunc("/api/cost", s.authMiddleware(s.cost))
	mux.HandleFunc("/api/audit", s.authMiddleware(s.audit))
	mux.HandleFunc("/api/eval/run", s.authMiddleware(s.csrfMiddleware(s.evalRun)))
	mux.HandleFunc("/api/process/expire-ttl", s.authMiddleware(s.csrfMiddleware(s.expireTTL)))
	return mux
}

func (s *Server) apiIndex(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path == "/api/" || r.URL.Path == "/api" {
		http.Redirect(w, r, "/", http.StatusSeeOther)
		return
	}
	http.NotFound(w, r)
}

func (s *Server) index(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/" {
		http.NotFound(w, r)
		return
	}
	data, err := templates.ReadFile("templates/index.html")
	if err != nil {
		http.Error(w, "template not found", http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	_, _ = w.Write(data)
}

func (s *Server) auth(w http.ResponseWriter, r *http.Request) {
	pin := strings.TrimSpace(r.URL.Query().Get("pin"))
	username := cleanHandle(r.URL.Query().Get("username"))
	authMode := "password"
	if pin != "" {
		if !validFourDigitPIN(pin) {
			writeError(w, fmt.Errorf("pin must be 4 digits"))
			return
		}
		authMode = "pin"
		if username == "" {
			username = pinUserHandle(pin, clientIP(r))
		}
	} else {
		token := firstNonEmpty(r.URL.Query().Get("password"), r.URL.Query().Get("token"))
		if token != s.token {
			writeJSON(w, map[string]any{"error": "invalid token"})
			return
		}
	}
	if username == "" {
		writeError(w, fmt.Errorf("username required"))
		return
	}
	if _, err := s.store.UserByHandle(username); err != nil {
		if _, createErr := s.app.CreateUser(username, username, "", ""); createErr != nil {
			writeError(w, createErr)
			return
		}
	}
	s.SetAuthCookie(w)
	s.SetUserCookie(w, username)
	writeJSON(w, map[string]any{"ok": true, "username": username, "auth_mode": authMode})
}

func (s *Server) session(w http.ResponseWriter, r *http.Request) {
	username := currentUsername(r)
	if username == "" {
		writeError(w, fmt.Errorf("not logged in"))
		return
	}
	writeJSON(w, map[string]any{"username": username})
}

func (s *Server) state(w http.ResponseWriter, r *http.Request) {
	users := s.store.ListUsers()
	selected := currentUsername(r)
	if selected == "" {
		selected = r.URL.Query().Get("user")
	}
	if selected == "" && len(users) > 0 {
		selected = users[0].Handle
	}
	var user *domain.User
	if selected != "" {
		if u, err := s.store.UserByHandle(selected); err == nil {
			user = u
		}
	}
	var contexts []domain.ContextItem
	var assets []domain.SourceAsset
	var matches []domain.MatchResult
	if user != nil {
		contexts = s.store.ContextsByUser(user.ID)
		assets = s.store.AssetsByUser(user.ID)
		matches = s.store.MatchesByUser(user.ID)
	}
	writeJSON(w, map[string]any{
		"repository":  s.store.Describe(),
		"provider":    s.app.Provider.Name(),
		"users":       users,
		"selected":    selected,
		"contexts":    contexts,
		"assets":      assets,
		"matches":     matches,
		"privacy":     privacySummary(contexts, assets),
		"model_calls": modelCallSummary(s.store.ModelCalls()),
	})
}

func currentUsername(r *http.Request) string {
	if cookie, err := r.Cookie("ctx_user"); err == nil {
		return strings.TrimSpace(cookie.Value)
	}
	return ""
}

func (s *Server) demoSeed(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		methodNotAllowed(w)
		return
	}
	if err := ensureDemoUser(s.app, s.store, "kevin", "Kevin Li", "上海", "数据库工程师，关注 AI infra、数据库系统、咖啡、旅行和城市漫游"); err != nil {
		writeError(w, err)
		return
	}
	if err := ensureDemoUser(s.app, s.store, "amy", "Amy", "上海", "喜欢探店、展览、夜市和轻户外，也对科技展、AI infra 展示和创业活动感兴趣"); err != nil {
		writeError(w, err)
		return
	}
	if err := ensureDemoNote(s.app, s.store, "kevin", "preference", "最近想认识同城、对 AI infra 和数据库系统感兴趣、周末可以一起喝咖啡或 citywalk 的人"); err != nil {
		writeError(w, err)
		return
	}
	if err := ensureDemoNote(s.app, s.store, "amy", "preference", "希望认识同城、喜欢展览、夜市、探店、AI infra 话题和轻松周末活动的人"); err != nil {
		writeError(w, err)
		return
	}
	if err := ensureDemoNote(s.app, s.store, "kevin", "safety_fixture", "private: Kevin 的精确 GPS 和私人行程不应该进入 match 或 bridge"); err != nil {
		writeError(w, err)
		return
	}
	writeJSON(w, map[string]any{"ok": true})
}

func (s *Server) process(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		methodNotAllowed(w)
		return
	}
	user := firstNonEmpty(currentUsername(r), r.URL.Query().Get("user"))
	items, err := s.app.Process(user, 100)
	if err != nil {
		writeError(w, err)
		return
	}
	writeJSON(w, map[string]any{"created": items})
}

func (s *Server) embed(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		methodNotAllowed(w)
		return
	}
	user := firstNonEmpty(currentUsername(r), r.URL.Query().Get("user"))
	if r.URL.Query().Get("all") == "true" {
		type userResult struct {
			User     string `json:"user"`
			Count    int    `json:"count"`
			Provider string `json:"provider"`
			Model    string `json:"model"`
			Fallback bool   `json:"fallback"`
			Error    string `json:"error,omitempty"`
		}
		var out []userResult
		for _, u := range s.store.ListUsers() {
			count, result, err := s.app.EmbedUserContexts(u.Handle)
			item := userResult{
				User:     u.Handle,
				Count:    count,
				Provider: result.Provider,
				Model:    result.Model,
				Fallback: result.FallbackUsed,
				Error:    result.Error,
			}
			if err != nil {
				item.Error = err.Error()
			}
			out = append(out, item)
		}
		writeJSON(w, map[string]any{"users": out})
		return
	}
	count, result, err := s.app.EmbedUserContexts(user)
	if err != nil {
		writeError(w, err)
		return
	}
	writeJSON(w, map[string]any{"count": count, "provider": result.Provider, "model": result.Model, "fallback": result.FallbackUsed, "error": result.Error})
}

func (s *Server) match(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		methodNotAllowed(w)
		return
	}
	user := firstNonEmpty(currentUsername(r), r.URL.Query().Get("user"))
	semantic := r.URL.Query().Get("semantic") == "true"
	var (
		results []domain.MatchResult
		err     error
	)
	if semantic {
		results, err = s.app.MatchSemantic(user, 5)
	} else {
		results, err = s.app.Match(user, 5)
	}
	if err != nil {
		writeError(w, err)
		return
	}
	writeJSON(w, map[string]any{"results": results})
}

func (s *Server) addNote(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		methodNotAllowed(w)
		return
	}
	if err := r.ParseForm(); err != nil {
		writeError(w, err)
		return
	}
	item, err := s.app.AddNote(
		firstNonEmpty(currentUsername(r), r.FormValue("user")),
		firstNonEmpty(r.FormValue("type"), "preference"),
		r.FormValue("text"),
		domain.ParseVisibility(r.FormValue("visibility"), domain.VisibilityMatchOnly),
		domain.ParsePurposes(firstNonEmpty(r.FormValue("purpose"), "self_memory,matching,generation"), nil),
	)
	if err != nil {
		writeError(w, err)
		return
	}
	writeJSON(w, item)
}

func (s *Server) chat(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		methodNotAllowed(w)
		return
	}
	if err := r.ParseForm(); err != nil {
		writeError(w, err)
		return
	}
	user := firstNonEmpty(currentUsername(r), r.FormValue("user"))
	text := strings.TrimSpace(r.FormValue("text"))
	if user == "" {
		writeError(w, fmt.Errorf("user required"))
		return
	}
	if text == "" {
		writeError(w, fmt.Errorf("text required"))
		return
	}
	item, err := s.app.AddNote(
		user,
		firstNonEmpty(r.FormValue("type"), "feed"),
		text,
		domain.ParseVisibility(r.FormValue("visibility"), domain.VisibilityMatchOnly),
		domain.ParsePurposes(firstNonEmpty(r.FormValue("purpose"), "self_memory,matching,generation"), nil),
	)
	if err != nil {
		writeError(w, err)
		return
	}
	reply, err := s.app.CompanionReply(user, text)
	if err != nil {
		writeError(w, err)
		return
	}
	writeJSON(w, map[string]any{"context": item, "reply": reply})
}

func (s *Server) addPhoto(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		methodNotAllowed(w)
		return
	}
	r.Body = http.MaxBytesReader(w, r.Body, 64<<20)
	if err := r.ParseMultipartForm(64 << 20); err != nil {
		writeError(w, err)
		return
	}
	file, header, err := r.FormFile("photo")
	if err != nil {
		writeError(w, err)
		return
	}
	defer file.Close()
	uploadDir := filepath.Join(s.store.DataDirPath(), "uploads")
	if err := os.MkdirAll(uploadDir, 0o755); err != nil {
		writeError(w, err)
		return
	}
	tmpDir := filepath.Join(uploadDir, domain.NewID("upload"))
	if err := os.MkdirAll(tmpDir, 0o755); err != nil {
		writeError(w, err)
		return
	}
	defer os.RemoveAll(tmpDir)
	tmpPath := filepath.Join(tmpDir, filepath.Base(header.Filename))
	tmp, err := os.Create(tmpPath)
	if err != nil {
		writeError(w, err)
		return
	}
	if _, err := io.Copy(tmp, file); err != nil {
		_ = tmp.Close()
		writeError(w, err)
		return
	}
	if err := tmp.Close(); err != nil {
		writeError(w, err)
		return
	}
	asset, err := s.app.AddPhotoWithOptions(firstNonEmpty(currentUsername(r), r.FormValue("user")), tmpPath, service.PhotoIngestOptions{
		Album:      r.FormValue("album"),
		City:       r.FormValue("city"),
		District:   r.FormValue("district"),
		Visibility: domain.ParseVisibility(r.FormValue("visibility"), domain.VisibilityPrivate),
	})
	if err != nil {
		writeError(w, err)
		return
	}
	writeJSON(w, asset)
}

func (s *Server) assetFile(w http.ResponseWriter, r *http.Request) {
	id := r.URL.Query().Get("id")
	asset, err := s.store.AssetByID(id)
	if err != nil {
		http.NotFound(w, r)
		return
	}
	if asset.AssetType != "photo" || asset.URI == "" {
		http.NotFound(w, r)
		return
	}
	http.ServeFile(w, r, asset.URI)
}

func (s *Server) editContext(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		methodNotAllowed(w)
		return
	}
	if err := r.ParseForm(); err != nil {
		writeError(w, err)
		return
	}
	item, err := s.app.EditContext(r.FormValue("id"), r.FormValue("text"))
	if err != nil {
		writeError(w, err)
		return
	}
	writeJSON(w, item)
}

func (s *Server) bridge(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		methodNotAllowed(w)
		return
	}
	user := firstNonEmpty(currentUsername(r), r.URL.Query().Get("user"))
	target := r.URL.Query().Get("target")
	result, err := s.app.Bridge(user, target)
	if err != nil {
		writeError(w, err)
		return
	}
	writeJSON(w, result)
}

func (s *Server) approve(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		methodNotAllowed(w)
		return
	}
	id := r.URL.Query().Get("id")
	item, err := s.app.ApproveContext(id, domain.VisibilityMatchOnly, []domain.Purpose{domain.PurposeSelfMemory, domain.PurposeMatching, domain.PurposeGeneration})
	if err != nil {
		writeError(w, err)
		return
	}
	writeJSON(w, item)
}

func (s *Server) rejectContext(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		methodNotAllowed(w)
		return
	}
	id := r.URL.Query().Get("id")
	reason := r.URL.Query().Get("reason")
	item, err := s.app.RejectContext(id, reason)
	if err != nil {
		writeError(w, err)
		return
	}
	writeJSON(w, item)
}

func (s *Server) deleteContext(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		methodNotAllowed(w)
		return
	}
	user := firstNonEmpty(currentUsername(r), r.URL.Query().Get("user"))
	id := r.URL.Query().Get("id")
	item, err := s.app.DeleteContextByUser(user, id)
	if err != nil {
		writeError(w, err)
		return
	}
	writeJSON(w, map[string]any{"deleted": item.ID})
}

func (s *Server) deleteAsset(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		methodNotAllowed(w)
		return
	}
	id := r.URL.Query().Get("id")
	cascade := r.URL.Query().Get("cascade-contexts") == "true"
	asset, err := s.app.DeleteAsset(id, cascade)
	if err != nil {
		writeError(w, err)
		return
	}
	writeJSON(w, map[string]any{"deleted": asset.ID})
}

func (s *Server) addIntent(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		methodNotAllowed(w)
		return
	}
	if err := r.ParseForm(); err != nil {
		writeError(w, err)
		return
	}
	ttlRaw := firstNonEmpty(r.FormValue("ttl"), "14d")
	ttl, err := parseDuration(ttlRaw)
	if err != nil {
		writeError(w, fmt.Errorf("invalid ttl: %w", err))
		return
	}
	item, err := s.app.AddIntent(firstNonEmpty(currentUsername(r), r.FormValue("user")), r.FormValue("text"), ttl)
	if err != nil {
		writeError(w, err)
		return
	}
	writeJSON(w, item)
}

func (s *Server) cost(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, map[string]any{
		"calls": modelCallSummary(s.store.ModelCalls()),
	})
}

func (s *Server) audit(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, map[string]any{"audits": []any{}, "note": "audit query not yet implemented on store"})
}

func (s *Server) evalRun(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		methodNotAllowed(w)
		return
	}
	suite := firstNonEmpty(r.URL.Query().Get("suite"), "all")
	failures := 0
	if suite == "privacy" || suite == "all" {
		for _, item := range s.store.AllContexts() {
			if item.Visibility == domain.VisibilityPrivate {
				decision := s.app.Privacy.CanUseContext(item, item.UserID, domain.PurposeMatching, nil)
				if decision.Allowed {
					failures++
				}
			}
		}
	}
	if suite == "deletion" || suite == "all" {
		for _, item := range s.store.AllContexts() {
			if item.State == domain.StateDeleted {
				decision := s.app.Privacy.CanUseContext(item, item.UserID, domain.PurposeGeneration, nil)
				if decision.Allowed {
					failures++
				}
			}
		}
	}
	writeJSON(w, map[string]any{"suite": suite, "failures": failures})
}

func (s *Server) expireTTL(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		methodNotAllowed(w)
		return
	}
	count, err := s.app.ExpireTTL()
	if err != nil {
		writeError(w, err)
		return
	}
	writeJSON(w, map[string]any{"expired": count})
}

func parseDuration(s string) (time.Duration, error) {
	return time.ParseDuration(s)
}

func privacySummary(contexts []domain.ContextItem, assets []domain.SourceAsset) map[string]any {
	visibility := map[domain.Visibility]int{}
	high := 0
	for _, ctx := range contexts {
		visibility[ctx.Visibility]++
		if ctx.Sensitivity >= domain.SensitivitySensitive {
			high++
		}
	}
	photos := 0
	for _, asset := range assets {
		if asset.AssetType == "photo" {
			photos++
		}
	}
	return map[string]any{
		"contexts":         len(contexts),
		"photos":           photos,
		"private":          visibility[domain.VisibilityPrivate],
		"match_only":       visibility[domain.VisibilityMatchOnly],
		"public":           visibility[domain.VisibilityPublic],
		"high_sensitivity": high,
	}
}

func modelCallSummary(calls []domain.ModelCallLog) []map[string]any {
	type stat struct {
		key      string
		count    int
		fallback int
		failed   int
		latency  int64
	}
	stats := map[string]*stat{}
	for _, call := range calls {
		key := call.Provider + "/" + call.Model + "/" + call.TaskType
		if stats[key] == nil {
			stats[key] = &stat{key: key}
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
	var out []map[string]any
	for _, stat := range stats {
		avg := int64(0)
		if stat.count > 0 {
			avg = stat.latency / int64(stat.count)
		}
		out = append(out, map[string]any{
			"key":            stat.key,
			"count":          stat.count,
			"fallback":       stat.fallback,
			"failed":         stat.failed,
			"avg_latency_ms": avg,
		})
	}
	sort.Slice(out, func(i, j int) bool {
		return fmt.Sprint(out[i]["key"]) < fmt.Sprint(out[j]["key"])
	})
	return out
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

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	if err := json.NewEncoder(w).Encode(v); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
	}
}

func writeError(w http.ResponseWriter, err error) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(http.StatusBadRequest)
	_ = json.NewEncoder(w).Encode(map[string]any{"error": err.Error()})
}

func methodNotAllowed(w http.ResponseWriter) {
	http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if value != "" {
			return value
		}
	}
	return ""
}
