package jwt

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
	once           sync.Once
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
	jwkURL := config.Cfg.AuthenHost
	resp, err := http.Get(jwkURL)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

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
	once.Do(func() {
		jwk_data, err := GetRawJWK()
		if err != nil {
			return
		}
		publicKeyCache, err = BuildRSAKeyFromJWK(jwk_data.N, jwk_data.E)
	})
	if publicKeyCache == nil {
		return nil, errors.New("failed to get public key")
	}
	return publicKeyCache, nil
}
