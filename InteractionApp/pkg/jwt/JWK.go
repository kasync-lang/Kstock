package jwt

type JWK struct {
	E   string `json:"e"`
	Kid string `json:"kid"`
	Kty string `json:"kty"`
	N   string `json:"n"`
}
type JWKResponse struct {
	JWKData JWK `json:"jwk_data"`
}
