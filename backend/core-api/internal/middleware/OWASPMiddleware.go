package middleware

import "github.com/gin-gonic/gin"

func OWASPSecurityHeaders() gin.HandlerFunc {
	return func(c *gin.Context) {
		h := c.Writer.Header()

		
		h.Set("X-Content-Type-Options", "nosniff")

		
		h.Set("X-Frame-Options", "DENY")

		
		h.Set("X-XSS-Protection", "1; mode=block")

		// Ép HTTPS (chỉ bật khi đã dùng HTTPS thật)
		// max-age=1 năm, include subdomain, preload
		//h.Set("Strict-Transport-Security", "max-age=31536000; includeSubDomains; preload")

		h.Set("Referrer-Policy", "no-referrer")

		
		h.Set("Content-Security-Policy", "default-src 'none'")

		
		h.Set("Cross-Origin-Opener-Policy", "same-origin")
		h.Set("Cross-Origin-Resource-Policy", "same-origin")
		h.Set("Cross-Origin-Embedder-Policy", "require-corp")

		h.Set("Permissions-Policy", "geolocation=(), microphone=(), camera=()")

		c.Next()
	}
}
