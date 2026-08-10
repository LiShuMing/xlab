# SP5 — Web 收尾 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** HTML extraction + embed.FS, token auth, CSRF, API alignment, test coverage.

**Architecture:** Extract inline HTML to `templates/`, add auth.go + csrf.go middleware, expand Routes() with 8 new endpoints.

**Tech Stack:** Go 1.25, embed.FS, net/http (no framework).

---

### Task 1: HTML extraction + embed.FS

**Files:**
- Create: `internal/web/templates/index.html`
- Modify: `internal/web/server.go`

- [ ] **Step 1: Extract HTML to index.html**

Cut the entire `const indexHTML = `...`` block (lines 434-768) from server.go. Paste into `internal/web/templates/index.html` as plain HTML (no Go string wrapping).

- [ ] **Step 2: Add embed.FS**

```go
import "embed"

//go:embed templates/*
var templates embed.FS
```

- [ ] **Step 3: Serve from embed**

Change `index()` handler:
```go
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
```

- [ ] **Step 4: Verify + Commit**

```bash
go build ./... && go test ./... -count=1
git add internal/web/templates/ internal/web/server.go
git commit -m "refactor(web): extract inline HTML to templates/ with embed.FS"
```

---

### Task 2: Token auth middleware

**Files:**
- Create: `internal/web/auth.go`
- Modify: `internal/web/server.go`
- Modify: `cmd/ctx-web/main.go`

- [ ] **Step 1: Create auth.go**

```go
package web

import (
    "crypto/rand"
    "encoding/hex"
    "net/http"
    "strings"
)

func generateToken() string {
    b := make([]byte, 32)
    _, _ = rand.Read(b)
    return hex.EncodeToString(b)
}

func authMiddleware(token string, next http.HandlerFunc) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        // Check Authorization header
        auth := r.Header.Get("Authorization")
        if strings.HasPrefix(auth, "Bearer ") {
            if strings.TrimPrefix(auth, "Bearer ") == token {
                next(w, r)
                return
            }
        }
        // Check cookie
        if cookie, err := r.Cookie("ctx_token"); err == nil && cookie.Value == token {
            next(w, r)
            return
        }
        w.Header().Set("Content-Type", "application/json; charset=utf-8")
        w.WriteHeader(http.StatusUnauthorized)
        _ = json.NewEncoder(w).Encode(map[string]any{"error": "unauthorized"})
    }
}
```

Need to import `crypto/rand`, `encoding/hex`, `strings`, and `encoding/json` (already imported in server.go, but auth.go is separate).

- [ ] **Step 2: Add token to Server struct**

Add `token string` field to Server struct. Update `NewServer` to accept and store it.

- [ ] **Step 3: Wrap all /api/* routes**

In `Routes()`, wrap all `/api/*` handlers with `authMiddleware`.

- [ ] **Step 4: Update main.go**

Read token from config or generate:
```go
token := cfg.Server.AuthToken
if token == "" {
    token = web.GenerateToken()
    log.Printf("generated auth token: %s", token)
}
server := web.NewServer(app, store, token)
```

Check if `config.ServerConfig` has an `AuthToken` field. If not, add it to `internal/config/config.go`:
```go
type ServerConfig struct {
    ListenAddr string `mapstructure:"listen_addr"`
    AuthToken  string `mapstructure:"auth_token"`
}
```

Also add to ctx.yaml.example.

- [ ] **Step 5: Verify + Commit**

```bash
go build ./... && go test ./... -count=1
git add internal/web/auth.go internal/web/server.go internal/config/config.go cmd/ctx-web/main.go ctx.yaml.example
git commit -m "feat(web): add token auth middleware for all API routes"
```

---

### Task 3: CSRF middleware

**Files:**
- Create: `internal/web/csrf.go`
- Modify: `internal/web/server.go`

- [ ] **Step 1: Create csrf.go**

Double-submit cookie pattern:
```go
package web

import (
    "crypto/rand"
    "encoding/hex"
    "net/http"
)

func csrfToken() string {
    b := make([]byte, 16)
    _, _ = rand.Read(b)
    return hex.EncodeToString(b)
}

func csrfMiddleware(next http.HandlerFunc) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        // GET/HEAD/OPTIONS are safe
        if r.Method == http.MethodGet || r.Method == http.MethodHead || r.Method == http.MethodOptions {
            next(w, r)
            return
        }
        // Set CSRF cookie if not present
        if _, err := r.Cookie("ctx_csrf"); err != nil {
            http.SetCookie(w, &http.Cookie{
                Name:     "ctx_csrf",
                Value:    csrfToken(),
                Path:     "/",
                SameSite: http.SameSiteStrictMode,
                HttpOnly: false, // JS needs to read it
            })
        }
        // Verify header matches cookie
        cookie, err := r.Cookie("ctx_csrf")
        if err != nil {
            http.Error(w, "csrf token required", http.StatusForbidden)
            return
        }
        header := r.Header.Get("X-CSRF-Token")
        if header == "" {
            header = r.Header.Get("X-Csrf-Token")
        }
        if cookie.Value == "" || header == "" || cookie.Value != header {
            http.Error(w, "csrf token mismatch", http.StatusForbidden)
            return
        }
        next(w, r)
    }
}
```

- [ ] **Step 2: Add CSRF endpoint for token retrieval**

Add a GET endpoint `/api/csrf` that sets the CSRF cookie and returns the token value (so JS can read it from response body if cookie is HttpOnly... but we need HttpOnly=false for JS to read).

Actually — simpler approach: the first POST request sets the cookie and the JS reads it from `document.cookie`. Add a GET `/api/csrf` endpoint that just ensures the cookie is set.

- [ ] **Step 3: Wrap POST endpoints**

In Routes(), wrap all POST handlers with `csrfMiddleware` (on top of authMiddleware).

- [ ] **Step 4: Update frontend JS**

Add a function to read CSRF cookie and include `X-CSRF-Token` header in all POST requests. Modify the `api()` and `postForm()` functions in index.html.

- [ ] **Step 5: Verify + Commit**

```bash
go build ./... && go test ./... -count=1
git add internal/web/csrf.go internal/web/server.go internal/web/templates/index.html
git commit -m "feat(web): add CSRF double-submit cookie middleware"
```

---

### Task 4: API alignment — add 8 missing endpoints

**Files:**
- Modify: `internal/web/server.go`

- [ ] **Step 1: Add handlers**

Add these handler methods to Server:

1. **rejectContext** — `POST /api/context/reject` → `app.RejectContext(id, reason)`
2. **deleteContext** — `POST /api/context/delete` → `app.DeleteContextByUser(user, id)`
3. **deleteAsset** — `POST /api/asset/delete` → `app.DeleteAsset(id, cascade)`
4. **addIntent** — `POST /api/intent` → `app.AddIntent(user, text, ttl)`
5. **cost** — `GET /api/cost` → render model call summary (same as CLI)
6. **audit** — `GET /api/audit?user=HANDLE` → list audit entries for user
7. **evalRun** — `POST /api/eval/run` → run eval suite
8. **expireTTL** — `POST /api/process/expire-ttl` → `app.ExpireTTL()`

- [ ] **Step 2: Register routes**

Add to `Routes()`:
```go
mux.HandleFunc("/api/context/reject", s.auth(s.csrf(s.rejectContext)))
mux.HandleFunc("/api/context/delete", s.auth(s.csrf(s.deleteContext)))
mux.HandleFunc("/api/asset/delete", s.auth(s.csrf(s.deleteAsset)))
mux.HandleFunc("/api/intent", s.auth(s.csrf(s.addIntent)))
mux.HandleFunc("/api/cost", s.auth(s.cost))
mux.HandleFunc("/api/audit", s.auth(s.audit))
mux.HandleFunc("/api/eval/run", s.auth(s.csrf(s.evalRun)))
mux.HandleFunc("/api/process/expire-ttl", s.auth(s.csrf(s.expireTTL)))
```

- [ ] **Step 3: Update frontend HTML**

Add UI elements for the new endpoints (buttons for context delete, asset delete, intent set, expire-ttl; display sections for cost/audit).

- [ ] **Step 4: Verify + Commit**

```bash
go build ./... && go test ./... -count=1
git add internal/web/server.go internal/web/templates/index.html
git commit -m "feat(web): add 8 API endpoints to align with CLI"
```

---

### Task 5: Photo upload cleanup hardening

**Files:**
- Modify: `internal/web/server.go`

- [ ] **Step 1: Review and fix cleanup**

Current code uses `defer os.RemoveAll(tmpDir)` which is good. But MaxBytesReader returns an error BEFORE ParseMultipartForm is called, so tmpDir might not be created yet (no cleanup needed in that case). Verify the flow:

1. `r.Body = http.MaxBytesReader(w, r.Body, 64<<20)` — if exceeded, `ParseMultipartForm` returns error, no tmpDir created ✓
2. `os.MkdirAll(tmpDir, ...)` fails — no tmpDir ✓
3. `os.Create(tmpPath)` fails — tmpDir created but will be cleaned by defer ✓
4. `io.Copy` fails — same as above ✓
5. `tmp.Close()` fails — same ✓

The only gap: if `ParseMultipartForm` succeeds but `FormFile("photo")` fails, tmpDir is never created and defer is safe. Current flow looks correct. Add explicit check and early return on the error paths that don't create tmpDir.

- [ ] **Step 2: Add explicit error handling comment**

No code change needed — the `defer os.RemoveAll(tmpDir)` right after `os.MkdirAll` already handles cleanup. Add a comment explaining the cleanup guarantee.

- [ ] **Step 3: Verify**

```bash
go build ./... && go test ./... -count=1
```

No commit needed if no code changes.

---

### Task 6: Server test expansion

**Files:**
- Modify: `internal/web/server_test.go`

- [ ] **Step 1: Read current test structure**

Read the existing test file to understand patterns used.

- [ ] **Step 2: Add auth failure tests**

For each endpoint, test that requests without token return 401:
```go
func TestAuthRequired(t *testing.T) {
    // For each API path:
    //   GET/POST without token → 401
    //   GET/POST with wrong token → 401
}
```

- [ ] **Step 3: Add happy path tests for new endpoints**

Test the 8 new endpoints with valid token:
- reject context
- delete context
- delete asset with cascade
- add intent
- cost summary
- audit listing
- eval run
- expire-ttl

- [ ] **Step 4: Verify + Commit**

```bash
go test ./... -count=1 -v
git add internal/web/server_test.go
git commit -m "test(web): expand server tests for auth + new endpoints"
```

---

### Task 7: Full regression

- [ ] **Step 1: All tests**

```bash
go test ./... -count=1 -v 2>&1 | tail -50
```

- [ ] **Step 2: Build both binaries**

```bash
go build ./cmd/ctx/ ./cmd/ctx-web/ && echo "both build ok"
```

- [ ] **Step 3: Demo flow**

```bash
go run ./cmd/ctx --data $(mktemp -d) demo run 2>&1 | head -10
```

- [ ] **Step 4: Web server smoke test**

```bash
# Start server, verify it responds
```

---

### 验收标准

1. `go build ./... && go test ./...` 通过
2. 无 token → 401；有 token → 200
3. CSRF cookie + header 校验生效
4. HTML 从模板文件加载（embed.FS）
5. 新增 8 个端点均可用
6. Photo 上传错误路径无泄漏
7. 测试覆盖每个 API happy + auth fail
8. Demo 无回归
