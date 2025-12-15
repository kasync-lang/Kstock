package middleware

import (
	"github.com/gin-gonic/gin"
	"net/http"
	"strings"
)

func AuthMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		auth_header := c.Request.Header.Get("Authorization")
		if auth_header == "" {

			c.JSON(http.StatusBadRequest, gin.H{"error": "Authorization header is missing"})
			c.Abort()
			return
		}
		bearer_token := strings.Split(auth_header, " ")
		if bearer_token[0] != "Bearer" {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid Authorization header format"})
			c.Abort()
			return
		}

	}
}
