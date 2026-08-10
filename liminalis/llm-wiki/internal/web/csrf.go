package web

import (
	"crypto/rand"
	"encoding/hex"
	"net/http"
)

func newCSRFToken() string {
	b := make([]byte, 16)
	_, _ = rand.Read(b)
	return hex.EncodeToString(b)
}

// csrfMiddleware validates CSRF double-submit cookie on mutating methods.
func (s *Server) csrfMiddleware(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// Safe methods skip CSRF check
		if r.Method == http.MethodGet || r.Method == http.MethodHead || r.Method == http.MethodOptions {
			next(w, r)
			return
		}

		// Ensure CSRF cookie is set
		if _, err := r.Cookie("ctx_csrf"); err != nil {
			http.SetCookie(w, &http.Cookie{
				Name:     "ctx_csrf",
				Value:    newCSRFToken(),
				Path:     "/",
				SameSite: http.SameSiteStrictMode,
				HttpOnly: false, // JS needs to read this
			})
		}

		// Verify cookie matches header
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

func (s *Server) csrfHandler(w http.ResponseWriter, r *http.Request) {
	// Always set a fresh CSRF cookie
	token := newCSRFToken()
	http.SetCookie(w, &http.Cookie{
		Name:     "ctx_csrf",
		Value:    token,
		Path:     "/",
		SameSite: http.SameSiteStrictMode,
		HttpOnly: false,
	})
	writeJSON(w, map[string]any{"csrf_token": token})
}
