package jwk

import (
	"Kstock/internal/config"
	"encoding/base64"
	"net/http"
	"net/http/httptest"
	"sync"
	"sync/atomic"
	"testing"
)

func TestBuildRSAKeyFromJWK(t *testing.T) {
	n := base64.RawURLEncoding.EncodeToString([]byte{0x01, 0x02, 0x03})
	e := base64.RawURLEncoding.EncodeToString([]byte{0x01, 0x00, 0x01})
	key, err := BuildRSAKeyFromJWK(n, e)
	if err != nil {
		t.Fatalf("BuildRSAKeyFromJWK error: %v", err)
	}
	if key.N.String() != "66051" || key.E != 65537 {
		t.Fatalf("key = %+v", key)
	}
	if _, err := BuildRSAKeyFromJWK("%", e); err == nil {
		t.Fatal("invalid modulus encoding succeeded")
	}
	zero := base64.RawURLEncoding.EncodeToString([]byte{0})
	if _, err := BuildRSAKeyFromJWK(n, zero); err == nil {
		t.Fatal("zero exponent succeeded")
	}
	tooLarge := base64.RawURLEncoding.EncodeToString([]byte{0x80, 0, 0, 0})
	if _, err := BuildRSAKeyFromJWK(n, tooLarge); err == nil {
		t.Fatal("large exponent succeeded")
	}
}

func TestGetKeystoreLazyLoadsCachesAndRetries(t *testing.T) {
	n := base64.RawURLEncoding.EncodeToString([]byte{0x01, 0x02, 0x03})
	e := base64.RawURLEncoding.EncodeToString([]byte{0x01, 0x00, 0x01})
	var requests atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if requests.Add(1) == 1 {
			http.Error(w, "temporary error", http.StatusServiceUnavailable)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"jwk_data":{"n":"` + n + `","e":"` + e + `"}}`))
	}))
	defer server.Close()

	previousConfig := config.Cfg
	config.Cfg = &config.Config{AuthenHost: server.URL}
	publicKeyMu.Lock()
	publicKeyCache = nil
	publicKeyMu.Unlock()
	t.Cleanup(func() {
		config.Cfg = previousConfig
		publicKeyMu.Lock()
		publicKeyCache = nil
		publicKeyMu.Unlock()
	})

	if _, err := GetKeystore(); err == nil {
		t.Fatal("unsuccessful JWK response was cached or treated as valid")
	}
	key, err := GetKeystore()
	if err != nil {
		t.Fatalf("retrying JWK fetch failed: %v", err)
	}
	if key.E != 65537 {
		t.Fatalf("key exponent = %d", key.E)
	}
	if _, err := GetKeystore(); err != nil {
		t.Fatalf("cached JWK lookup failed: %v", err)
	}
	if requests.Load() != 2 {
		t.Fatalf("JWK requests = %d, want 2", requests.Load())
	}
}

func TestGetKeystoreConcurrentLazyLoadFetchesOnce(t *testing.T) {
	n := base64.RawURLEncoding.EncodeToString([]byte{0x01, 0x02, 0x03})
	e := base64.RawURLEncoding.EncodeToString([]byte{0x01, 0x00, 0x01})
	var requests atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests.Add(1)
		_, _ = w.Write([]byte(`{"jwk_data":{"n":"` + n + `","e":"` + e + `"}}`))
	}))
	defer server.Close()

	previousConfig := config.Cfg
	config.Cfg = &config.Config{AuthenHost: server.URL}
	publicKeyMu.Lock()
	publicKeyCache = nil
	publicKeyMu.Unlock()
	t.Cleanup(func() {
		config.Cfg = previousConfig
		publicKeyMu.Lock()
		publicKeyCache = nil
		publicKeyMu.Unlock()
	})

	const callers = 20
	errs := make(chan error, callers)
	var wg sync.WaitGroup
	for range callers {
		wg.Go(func() {
			_, err := GetKeystore()
			errs <- err
		})
	}
	wg.Wait()
	close(errs)
	for err := range errs {
		if err != nil {
			t.Fatalf("concurrent JWK lookup failed: %v", err)
		}
	}
	if requests.Load() != 1 {
		t.Fatalf("JWK requests = %d, want 1", requests.Load())
	}
}
