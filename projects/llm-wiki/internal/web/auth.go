package web

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"net"
	"net/http"
	"strings"
	"unicode"
)

// GenerateToken creates a random 64-character hex token.
func GenerateToken() string {
	b := make([]byte, 32)
	_, _ = rand.Read(b)
	return hex.EncodeToString(b)
}

// authMiddleware protects routes with Bearer token or cookie auth.
func (s *Server) authMiddleware(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// Check Authorization header
		auth := r.Header.Get("Authorization")
		if strings.HasPrefix(auth, "Bearer ") {
			if strings.TrimPrefix(auth, "Bearer ") == s.token {
				next(w, r)
				return
			}
		}
		// Check cookie fallback
		if cookie, err := r.Cookie("ctx_token"); err == nil && cookie.Value == s.token {
			next(w, r)
			return
		}
		w.Header().Set("Content-Type", "application/json; charset=utf-8")
		w.WriteHeader(http.StatusUnauthorized)
		_ = json.NewEncoder(w).Encode(map[string]any{"error": "unauthorized"})
	}
}

// SetAuthCookie sets the auth token as a cookie on the response.
func (s *Server) SetAuthCookie(w http.ResponseWriter) {
	http.SetCookie(w, &http.Cookie{
		Name:     "ctx_token",
		Value:    s.token,
		Path:     "/",
		HttpOnly: true,
		SameSite: http.SameSiteStrictMode,
	})
}

func (s *Server) SetUserCookie(w http.ResponseWriter, username string) {
	http.SetCookie(w, &http.Cookie{
		Name:     "ctx_user",
		Value:    username,
		Path:     "/",
		HttpOnly: true,
		SameSite: http.SameSiteStrictMode,
	})
}

func clientIP(r *http.Request) string {
	if forwarded := strings.TrimSpace(r.Header.Get("X-Forwarded-For")); forwarded != "" {
		parts := strings.Split(forwarded, ",")
		if ip := strings.TrimSpace(parts[0]); ip != "" {
			return ip
		}
	}
	if realIP := strings.TrimSpace(r.Header.Get("X-Real-IP")); realIP != "" {
		return realIP
	}
	host, _, err := net.SplitHostPort(r.RemoteAddr)
	if err == nil && host != "" {
		return host
	}
	return strings.TrimSpace(r.RemoteAddr)
}

func pinUserHandle(pin, ip string) string {
	sum := sha256.Sum256([]byte(ip + ":" + pin))
	return "pin_" + hex.EncodeToString(sum[:])[:12]
}

func validFourDigitPIN(pin string) bool {
	if len(pin) != 4 {
		return false
	}
	for _, r := range pin {
		if r < '0' || r > '9' {
			return false
		}
	}
	return true
}

func cleanHandle(raw string) string {
	raw = strings.TrimSpace(raw)
	var b strings.Builder
	for _, r := range raw {
		if unicode.IsLetter(r) || unicode.IsDigit(r) || r == '_' || r == '-' {
			b.WriteRune(unicode.ToLower(r))
		}
	}
	return b.String()
}
