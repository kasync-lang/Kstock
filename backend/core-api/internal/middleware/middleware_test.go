package middleware

import (
	"crypto/rand"
	"crypto/rsa"
	"encoding/base64"
	"encoding/json"
	"math/big"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"Kstock/internal/config"
	"Kstock/internal/dto"
	"Kstock/pkg/jwk"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
)

func testRouter(handlers ...gin.HandlerFunc) *gin.Engine {
	gin.SetMode(gin.TestMode)
	r := gin.New()
	r.GET("/", append(handlers, func(c *gin.Context) { c.Status(http.StatusNoContent) })...)
	return r
}

func setupJWKServer(t *testing.T) (*rsa.PrivateKey, string) {
	t.Helper()
	privKey, err := rsa.GenerateKey(rand.Reader, 2048)
	if err != nil {
		t.Fatalf("rsa.GenerateKey failed: %v", err)
	}

	n := base64.RawURLEncoding.EncodeToString(privKey.N.Bytes())
	eBytes := big.NewInt(int64(privKey.E)).Bytes()
	e := base64.RawURLEncoding.EncodeToString(eBytes)

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{
			"jwk_data": map[string]string{
				"n": n,
				"e": e,
			},
		})
	}))
	t.Cleanup(server.Close)

	return privKey, server.URL
}

func TestOWASPSecurityHeaders(t *testing.T) {
	r := testRouter(OWASPSecurityHeaders())
	w := httptest.NewRecorder()
	r.ServeHTTP(w, httptest.NewRequest(http.MethodGet, "/", nil))
	for key, want := range map[string]string{
		"X-Content-Type-Options":  "nosniff",
		"X-Frame-Options":         "DENY",
		"Content-Security-Policy": "default-src 'none'",
		"Referrer-Policy":         "no-referrer",
	} {
		if got := w.Header().Get(key); got != want {
			t.Errorf("%s = %q, want %q", key, got, want)
		}
	}
}

func TestInjectPriceStore(t *testing.T) {
	store := dto.NewPriceStore()
	store.Update("USD", 1)
	gin.SetMode(gin.TestMode)
	r := gin.New()
	r.GET("/", InjectPriceStore(store), func(c *gin.Context) {
		got, ok := c.Get("price_store")
		if !ok || got != store {
			t.Error("price store was not injected into the context")
		}
		c.Status(http.StatusNoContent)
	})
	w := httptest.NewRecorder()
	r.ServeHTTP(w, httptest.NewRequest(http.MethodGet, "/", nil))
	if w.Code != http.StatusNoContent {
		t.Fatalf("status = %d, want %d", w.Code, http.StatusNoContent)
	}
}

func TestRateLimitPerIPAndRefill(t *testing.T) {
	r := testRouter(RateLimit(2, 20*time.Millisecond))
	request := func(ip string) int {
		req := httptest.NewRequest(http.MethodGet, "/", nil)
		req.RemoteAddr = ip + ":1234"
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)
		return w.Code
	}
	if got := request("192.0.2.1"); got != http.StatusNoContent {
		t.Fatalf("first request status = %d", got)
	}
	if got := request("192.0.2.1"); got != http.StatusNoContent {
		t.Fatalf("second request status = %d", got)
	}
	if got := request("192.0.2.1"); got != http.StatusTooManyRequests {
		t.Fatalf("limited request status = %d", got)
	}
	if got := request("192.0.2.2"); got != http.StatusNoContent {
		t.Fatalf("other IP status = %d", got)
	}
	time.Sleep(25 * time.Millisecond)
	if got := request("192.0.2.1"); got != http.StatusNoContent {
		t.Fatalf("refilled request status = %d", got)
	}
}

func TestAuthMiddlewareRejectsMissingAndMalformedHeaders(t *testing.T) {
	for _, authorization := range []string{"", "Token value", "Bearer", "Bearer "} {
		gin.SetMode(gin.TestMode)
		r := gin.New()
		r.GET("/", AuthMiddleware(), func(c *gin.Context) { c.Status(http.StatusNoContent) })
		req := httptest.NewRequest(http.MethodGet, "/", nil)
		if authorization != "" {
			req.Header.Set("Authorization", authorization)
		}
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)
		if w.Code != http.StatusUnauthorized {
			t.Errorf("Authorization %q returned status %d, want %d", authorization, w.Code, http.StatusUnauthorized)
		}

		var resp AuthErrorResponse
		if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
			t.Fatalf("failed to decode response body: %v", err)
		}
		if resp.Code != "MISSING_TOKEN" || resp.Message != "Bearer token is required" {
			t.Errorf("Authorization %q returned %+v, want code=MISSING_TOKEN, message=Bearer token is required", authorization, resp)
		}
	}
}

func TestAuthMiddlewareRejectsInvalidToken(t *testing.T) {
	gin.SetMode(gin.TestMode)
	r := gin.New()
	r.GET("/", AuthMiddleware(), func(c *gin.Context) { c.Status(http.StatusNoContent) })
	req := httptest.NewRequest(http.MethodGet, "/", nil)
	req.Header.Set("Authorization", "Bearer invalid.token.string")
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want %d", w.Code, http.StatusUnauthorized)
	}

	var resp AuthErrorResponse
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}
	if resp.Code != "INVALID_TOKEN" || resp.Message != "Token is invalid" {
		t.Errorf("got %+v, want code=INVALID_TOKEN, message=Token is invalid", resp)
	}
}

func TestAuthMiddlewareRejectsExpiredToken(t *testing.T) {
	privKey, jwkURL := setupJWKServer(t)

	prevCfg := config.Cfg
	config.Cfg = &config.Config{AuthenHost: jwkURL}
	jwk.ResetKeystoreCacheForTest()
	t.Cleanup(func() {
		config.Cfg = prevCfg
		jwk.ResetKeystoreCacheForTest()
	})

	claims := jwt.MapClaims{
		"sub": "user-expired",
		"exp": time.Now().Add(-10 * time.Minute).Unix(),
	}
	token := jwt.NewWithClaims(jwt.SigningMethodRS256, claims)
	tokenStr, err := token.SignedString(privKey)
	if err != nil {
		t.Fatalf("failed to sign token: %v", err)
	}

	gin.SetMode(gin.TestMode)
	r := gin.New()
	r.GET("/", AuthMiddleware(), func(c *gin.Context) { c.Status(http.StatusNoContent) })
	req := httptest.NewRequest(http.MethodGet, "/", nil)
	req.Header.Set("Authorization", "Bearer "+tokenStr)
	w := httptest.NewRecorder()
	r.ServeHTTP(w, req)

	if w.Code != http.StatusUnauthorized {
		t.Fatalf("status = %d, want %d", w.Code, http.StatusUnauthorized)
	}

	var resp AuthErrorResponse
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}
	if resp.Code != "ACCESS_TOKEN_EXPIRED" || resp.Message != "Access token has expired" {
		t.Errorf("got %+v, want code=ACCESS_TOKEN_EXPIRED, message=Access token has expired", resp)
	}
}

func TestAuthSocketMiddleware(t *testing.T) {
	privKey, jwkURL := setupJWKServer(t)

	prevCfg := config.Cfg
	config.Cfg = &config.Config{AuthenHost: jwkURL}
	jwk.ResetKeystoreCacheForTest()
	t.Cleanup(func() {
		config.Cfg = prevCfg
		jwk.ResetKeystoreCacheForTest()
	})

	expiredClaims := jwt.MapClaims{
		"sub": "user-expired",
		"exp": time.Now().Add(-10 * time.Minute).Unix(),
	}
	expiredToken, err := jwt.NewWithClaims(jwt.SigningMethodRS256, expiredClaims).SignedString(privKey)
	if err != nil {
		t.Fatalf("failed to sign token: %v", err)
	}

	tests := []struct {
		name        string
		path        string
		authHeader  string
		wantCode    string
		wantMessage string
	}{
		{
			name:        "missing token entirely",
			path:        "/",
			wantCode:    "MISSING_TOKEN",
			wantMessage: "Bearer token is required",
		},
		{
			name:        "malformed auth header",
			path:        "/",
			authHeader:  "InvalidHeader",
			wantCode:    "MISSING_TOKEN",
			wantMessage: "Bearer token is required",
		},
		{
			name:        "invalid token query param",
			path:        "/?token=bad.token.signature",
			wantCode:    "INVALID_TOKEN",
			wantMessage: "Token is invalid",
		},
		{
			name:        "invalid token auth header",
			path:        "/",
			authHeader:  "Bearer bad.token.signature",
			wantCode:    "INVALID_TOKEN",
			wantMessage: "Token is invalid",
		},
		{
			name:        "expired token query param",
			path:        "/?token=" + expiredToken,
			wantCode:    "ACCESS_TOKEN_EXPIRED",
			wantMessage: "Access token has expired",
		},
		{
			name:        "expired token auth header",
			path:        "/",
			authHeader:  "Bearer " + expiredToken,
			wantCode:    "ACCESS_TOKEN_EXPIRED",
			wantMessage: "Access token has expired",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			gin.SetMode(gin.TestMode)
			r := gin.New()
			r.GET("/", AuthSocketMiddleware(), func(c *gin.Context) { c.Status(http.StatusNoContent) })
			req := httptest.NewRequest(http.MethodGet, tt.path, nil)
			if tt.authHeader != "" {
				req.Header.Set("Authorization", tt.authHeader)
			}
			w := httptest.NewRecorder()
			r.ServeHTTP(w, req)

			if w.Code != http.StatusUnauthorized {
				t.Fatalf("status = %d, want %d", w.Code, http.StatusUnauthorized)
			}

			var resp AuthErrorResponse
			if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
				t.Fatalf("failed to decode response: %v", err)
			}
			if resp.Code != tt.wantCode || resp.Message != tt.wantMessage {
				t.Errorf("got %+v, want code=%s, message=%s", resp, tt.wantCode, tt.wantMessage)
			}
		})
	}
}

