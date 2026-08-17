package middleware

import (
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"Kstock/internal/dto"

	"github.com/gin-gonic/gin"
)

func testRouter(handlers ...gin.HandlerFunc) *gin.Engine {
	gin.SetMode(gin.TestMode)
	r := gin.New()
	r.GET("/", append(handlers, func(c *gin.Context) { c.Status(http.StatusNoContent) })...)
	return r
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
	for _, authorization := range []string{"", "Token value", "Bearer"} {
		gin.SetMode(gin.TestMode)
		r := gin.New()
		r.GET("/", AuthMiddleware(), func(c *gin.Context) { c.Status(http.StatusNoContent) })
		req := httptest.NewRequest(http.MethodGet, "/", nil)
		if authorization != "" {
			req.Header.Set("Authorization", authorization)
		}
		w := httptest.NewRecorder()
		r.ServeHTTP(w, req)
		if w.Code != http.StatusBadRequest {
			t.Errorf("Authorization %q returned %d, want %d", authorization, w.Code, http.StatusBadRequest)
		}
	}
}
