package jwk

import (
	"encoding/base64"
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
