package web

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/LiShuMing/xlab/projects/llm-wiki/internal/provider"
	"github.com/LiShuMing/xlab/projects/llm-wiki/internal/repository"
	"github.com/LiShuMing/xlab/projects/llm-wiki/internal/service"
)

func TestServerDemoFlow(t *testing.T) {
	store, err := repository.OpenFile(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	if err := store.Init(); err != nil {
		t.Fatal(err)
	}
	app := service.NewAppWithProvider(store, provider.MockProvider{})
	token := "test-token"
	handler := NewServer(app, store, token).Routes()

	post(t, handler, "/api/demo/seed", token)
	state := getJSON(t, handler, "/api/state?user=kevin", token)
	if len(asSlice(t, state["users"])) != 2 {
		t.Fatalf("expected 2 demo users, got %#v", state["users"])
	}
	if len(asSlice(t, state["contexts"])) == 0 {
		t.Fatalf("expected demo contexts, got %#v", state["contexts"])
	}

	embed := post(t, handler, "/api/embed?all=true", token)
	embeddedUsers := asSlice(t, embed["users"])
	if len(embeddedUsers) != 2 {
		t.Fatalf("expected embeddings for 2 users, got %#v", embed)
	}

	match := post(t, handler, "/api/match?user=kevin&semantic=true", token)
	if len(asSlice(t, match["results"])) == 0 {
		t.Fatalf("expected semantic match result, got %#v", match)
	}

	bridge := post(t, handler, "/api/bridge?user=kevin&target=amy", token)
	reason, _ := bridge["connection_reason"].(string)
	if bridge["target_handle"] != "amy" || !strings.Contains(reason, "AI infra") {
		t.Fatalf("expected bridge text for kevin/amy, got %#v", bridge)
	}
}

func TestServerNoteEditAndPhotoUpload(t *testing.T) {
	store, err := repository.OpenFile(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	if err := store.Init(); err != nil {
		t.Fatal(err)
	}
	app := service.NewAppWithProvider(store, provider.MockProvider{})
	token := "test-token"
	handler := NewServer(app, store, token).Routes()
	post(t, handler, "/api/demo/seed", token)

	noteBody := strings.NewReader("user=kevin&type=preference&text=hello+web&visibility=match_only")
	req := httptest.NewRequest(http.MethodPost, "/api/note", noteBody)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("X-CSRF-Token", "test-csrf-token")
	req.AddCookie(&http.Cookie{Name: "ctx_csrf", Value: "test-csrf-token"})
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("add note returned %d: %s", rec.Code, rec.Body.String())
	}
	var note map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &note); err != nil {
		t.Fatal(err)
	}

	editBody := strings.NewReader("id=" + note["id"].(string) + "&text=hello+edited")
	req = httptest.NewRequest(http.MethodPost, "/api/context/edit", editBody)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("X-CSRF-Token", "test-csrf-token")
	req.AddCookie(&http.Cookie{Name: "ctx_csrf", Value: "test-csrf-token"})
	rec = httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("edit context returned %d: %s", rec.Code, rec.Body.String())
	}

	photo := uploadPhoto(t, handler, token)
	md, _ := photo["metadata"].(map[string]any)
	if photo["asset_type"] != "photo" || md["width"] != float64(1) || md["city"] != "上海" {
		t.Fatalf("expected uploaded photo metadata, got %#v", photo)
	}
}

func TestServerRejectsWrongMethod(t *testing.T) {
	store, err := repository.OpenFile(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	app := service.NewAppWithProvider(store, provider.MockProvider{})
	token := "test-token"
	handler := NewServer(app, store, token).Routes()

	req := httptest.NewRequest(http.MethodGet, "/api/demo/seed", nil)
	req.Header.Set("Authorization", "Bearer "+token)
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusMethodNotAllowed {
		t.Fatalf("expected 405, got %d", rec.Code)
	}
}

func post(t *testing.T, handler http.Handler, path, token string) map[string]any {
	t.Helper()
	req := httptest.NewRequest(http.MethodPost, path, nil)
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("X-CSRF-Token", "test-csrf-token")
	req.AddCookie(&http.Cookie{Name: "ctx_csrf", Value: "test-csrf-token"})
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("POST %s returned %d: %s", path, rec.Code, rec.Body.String())
	}
	var data map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &data); err != nil {
		t.Fatalf("decode %s: %v", path, err)
	}
	return data
}

func getJSON(t *testing.T, handler http.Handler, path, token string) map[string]any {
	t.Helper()
	req := httptest.NewRequest(http.MethodGet, path, nil)
	req.Header.Set("Authorization", "Bearer "+token)
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("GET %s returned %d: %s", path, rec.Code, rec.Body.String())
	}
	var data map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &data); err != nil {
		t.Fatalf("decode %s: %v", path, err)
	}
	return data
}

func asSlice(t *testing.T, v any) []any {
	t.Helper()
	items, ok := v.([]any)
	if !ok {
		t.Fatalf("expected JSON array, got %T", v)
	}
	return items
}

func TestAuthRequired(t *testing.T) {
	store, err := repository.OpenFile(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	if err := store.Init(); err != nil {
		t.Fatal(err)
	}
	app := service.NewAppWithProvider(store, provider.MockProvider{})
	token := "test-token"
	handler := NewServer(app, store, token).Routes()

	getEndpoints := []string{
		"/api/session",
		"/api/state",
		"/api/cost",
		"/api/audit",
	}
	for _, path := range getEndpoints {
		t.Run("no_token:"+path, func(t *testing.T) {
			req := httptest.NewRequest(http.MethodGet, path, nil)
			rec := httptest.NewRecorder()
			handler.ServeHTTP(rec, req)
			if rec.Code != http.StatusUnauthorized {
				t.Errorf("%s: got %d, want %d", path, rec.Code, http.StatusUnauthorized)
			}
		})
	}

	postEndpoints := []string{
		"/api/demo/seed",
		"/api/process",
		"/api/embed",
		"/api/match",
		"/api/bridge",
		"/api/chat",
		"/api/note",
		"/api/photo",
		"/api/context/edit",
		"/api/review/approve",
		"/api/context/reject",
		"/api/context/delete",
		"/api/asset/delete",
		"/api/intent",
		"/api/eval/run",
		"/api/process/expire-ttl",
	}
	for _, path := range postEndpoints {
		t.Run("no_token:"+path, func(t *testing.T) {
			req := httptest.NewRequest(http.MethodPost, path, nil)
			rec := httptest.NewRecorder()
			handler.ServeHTTP(rec, req)
			if rec.Code != http.StatusUnauthorized {
				t.Errorf("%s: got %d, want %d", path, rec.Code, http.StatusUnauthorized)
			}
		})
	}

	t.Run("wrong_token", func(t *testing.T) {
		req := httptest.NewRequest(http.MethodGet, "/api/state", nil)
		req.Header.Set("Authorization", "Bearer wrong-token")
		rec := httptest.NewRecorder()
		handler.ServeHTTP(rec, req)
		if rec.Code != http.StatusUnauthorized {
			t.Errorf("wrong token: got %d, want %d", rec.Code, http.StatusUnauthorized)
		}
	})
}

func TestPinLoginDerivesUserFromIP(t *testing.T) {
	store, err := repository.OpenFile(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	if err := store.Init(); err != nil {
		t.Fatal(err)
	}
	app := service.NewAppWithProvider(store, provider.MockProvider{})
	token := "test-token"
	handler := NewServer(app, store, token).Routes()

	req := httptest.NewRequest(http.MethodGet, "/api/auth?pin=1234", nil)
	req.RemoteAddr = "192.0.2.10:4567"
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("pin auth returned %d: %s", rec.Code, rec.Body.String())
	}
	var data map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &data); err != nil {
		t.Fatal(err)
	}
	username, _ := data["username"].(string)
	if !strings.HasPrefix(username, "pin_") {
		t.Fatalf("expected derived pin user, got %#v", data)
	}

	req = httptest.NewRequest(http.MethodGet, "/api/session", nil)
	for _, cookie := range rec.Result().Cookies() {
		req.AddCookie(cookie)
	}
	rec = httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("pin session returned %d: %s", rec.Code, rec.Body.String())
	}
}

func TestNewEndpoints(t *testing.T) {
	store, err := repository.OpenFile(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	if err := store.Init(); err != nil {
		t.Fatal(err)
	}
	app := service.NewAppWithProvider(store, provider.MockProvider{})
	token := "test-token"
	handler := NewServer(app, store, token).Routes()

	post(t, handler, "/api/demo/seed", token)

	t.Run("cost", func(t *testing.T) {
		data := getJSON(t, handler, "/api/cost", token)
		if _, ok := data["calls"]; !ok {
			t.Error("cost response missing calls key")
		}
	})

	t.Run("audit", func(t *testing.T) {
		data := getJSON(t, handler, "/api/audit", token)
		if _, ok := data["audits"]; !ok {
			t.Error("audit response missing audits key")
		}
	})

	t.Run("expire_ttl", func(t *testing.T) {
		data := post(t, handler, "/api/process/expire-ttl", token)
		if _, ok := data["expired"]; !ok {
			t.Error("expire-ttl response missing expired key")
		}
	})

	t.Run("eval_run", func(t *testing.T) {
		data := post(t, handler, "/api/eval/run", token)
		if _, ok := data["failures"]; !ok {
			t.Error("eval response missing failures key")
		}
	})

	t.Run("intent", func(t *testing.T) {
		body := strings.NewReader("user=kevin&text=test+intent&ttl=24h")
		req := httptest.NewRequest(http.MethodPost, "/api/intent", body)
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		req.Header.Set("Authorization", "Bearer "+token)
		req.Header.Set("X-CSRF-Token", "test-csrf-token")
		req.AddCookie(&http.Cookie{Name: "ctx_csrf", Value: "test-csrf-token"})
		rec := httptest.NewRecorder()
		handler.ServeHTTP(rec, req)
		if rec.Code != http.StatusOK {
			t.Errorf("intent: got status %d: %s", rec.Code, rec.Body.String())
		}
	})

	t.Run("chat", func(t *testing.T) {
		body := strings.NewReader("user=kevin&text=最近想找人聊聊+AI+infra&visibility=match_only")
		req := httptest.NewRequest(http.MethodPost, "/api/chat", body)
		req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
		req.Header.Set("Authorization", "Bearer "+token)
		req.Header.Set("X-CSRF-Token", "test-csrf-token")
		req.AddCookie(&http.Cookie{Name: "ctx_csrf", Value: "test-csrf-token"})
		rec := httptest.NewRecorder()
		handler.ServeHTTP(rec, req)
		if rec.Code != http.StatusOK {
			t.Errorf("chat: got status %d: %s", rec.Code, rec.Body.String())
			return
		}
		var data map[string]any
		if err := json.Unmarshal(rec.Body.Bytes(), &data); err != nil {
			t.Fatal(err)
		}
		if _, ok := data["reply"].(map[string]any); !ok {
			t.Fatalf("chat response missing reply: %#v", data)
		}
	})
}

func uploadPhoto(t *testing.T, handler http.Handler, token string) map[string]any {
	t.Helper()
	const png1x1 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGNgYGAAAAAEAAHIiL8YAAAAAElFTkSuQmCC"
	raw, err := base64.StdEncoding.DecodeString(png1x1)
	if err != nil {
		t.Fatal(err)
	}
	var body bytes.Buffer
	writer := multipart.NewWriter(&body)
	fields := map[string]string{
		"user":       "kevin",
		"album":      "web",
		"city":       "上海",
		"district":   "黄浦区",
		"visibility": "private",
	}
	for k, v := range fields {
		if err := writer.WriteField(k, v); err != nil {
			t.Fatal(err)
		}
	}
	part, err := writer.CreateFormFile("photo", "tiny.png")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := part.Write(raw); err != nil {
		t.Fatal(err)
	}
	if err := writer.Close(); err != nil {
		t.Fatal(err)
	}
	req := httptest.NewRequest(http.MethodPost, "/api/photo", &body)
	req.Header.Set("Content-Type", writer.FormDataContentType())
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("X-CSRF-Token", "test-csrf-token")
	req.AddCookie(&http.Cookie{Name: "ctx_csrf", Value: "test-csrf-token"})
	rec := httptest.NewRecorder()
	handler.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("upload photo returned %d: %s", rec.Code, rec.Body.String())
	}
	var data map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &data); err != nil {
		t.Fatal(err)
	}
	return data
}
