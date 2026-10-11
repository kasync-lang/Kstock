package jwk

import (
	"Kstock/internal/config"
	"crypto/rsa"
	"encoding/base64"
	"encoding/json"
	"errors"
	"io"
	"math/big"
	"net/http"
	"sync"
)

var (
	publicKeyCache *rsa.PublicKey
	publicKeyMu    sync.RWMutex
)

func BuildRSAKeyFromJWK(nB64Url, eB64Url string) (*rsa.PublicKey, error) {
	nBytes, err := base64.RawURLEncoding.DecodeString(nB64Url)
	if err != nil {
		return nil, err
	}

	eBytes, err := base64.RawURLEncoding.DecodeString(eB64Url)
	if err != nil {
		return nil, err
	}

	eInt := big.NewInt(0).SetBytes(eBytes).Int64()
	if eInt <= 0 || eInt > 1<<31-1 {
		return nil, errors.New("invalid exponent")
	}

	pub := &rsa.PublicKey{
		N: big.NewInt(0).SetBytes(nBytes),
		E: int(eInt),
	}
	return pub, nil
}
func GetRawJWK() (*JWK, error) {
	if config.Cfg == nil || config.Cfg.AuthenHost == "" {
		return nil, errors.New("JWK endpoint is not configured")
	}
	jwkURL := config.Cfg.AuthenHost
	resp, err := http.Get(jwkURL)

	if err != nil {
		return nil, err
	}

	defer resp.Body.Close()
	if resp.StatusCode < http.StatusOK || resp.StatusCode >= http.StatusMultipleChoices {
		return nil, errors.New("JWK endpoint returned an unsuccessful status")
	}
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	var r JWKResponse
	if err := json.Unmarshal(body, &r); err != nil {
		return nil, err
	}

	return &r.JWKData, nil

}

func GetKeystore() (*rsa.PublicKey, error) {
	publicKeyMu.RLock()
	key := publicKeyCache
	publicKeyMu.RUnlock()
	if key != nil {
		return key, nil
	}

	// Only one request fetches the JWK while the cache is empty. Other requests
	// wait here and reuse the cached key after a successful fetch.
	publicKeyMu.Lock()
	defer publicKeyMu.Unlock()
	if publicKeyCache != nil {
		return publicKeyCache, nil
	}

	jwkData, err := GetRawJWK()
	if err != nil {
		return nil, err
	}
	key, err = BuildRSAKeyFromJWK(jwkData.N, jwkData.E)
	if err != nil {
		return nil, err
	}
	publicKeyCache = key
	return publicKeyCache, nil
}

// ResetKeystoreCacheForTest clears the cached public key for testing purposes.
func ResetKeystoreCacheForTest() {
	publicKeyMu.Lock()
	defer publicKeyMu.Unlock()
	publicKeyCache = nil
}
