package middleware

import (
	"Kstock/internal/server"
	"Kstock/pkg/jwk"
	"net/http"
	"strings"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
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
		if bearer_token[0] != "Bearer" || len(bearer_token) != 2 {
			c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid Authorization header format"})
			c.Abort()
			return
		}
		tokenStr := bearer_token[1]

		claims, err := jwk.Verify(tokenStr)
		if err != nil {
			c.JSON(http.StatusUnauthorized, gin.H{"error": "Invalid token"})
			c.Abort()
			return
		}

		TemporaryRegiterUser(claims, c)
		c.Set("claims", claims)
		c.Next()
	}
}
func TemporaryRegiterUser(claims jwt.Claims, c *gin.Context) {
	sub, err := claims.(jwt.MapClaims).GetSubject()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to Register user"})
		c.Abort()
		return
	}
	db := server.GetDB()
	query_insert := `insert into "user" (user_id) values ($1) on conflict (user_id) do nothing`
	tx := db.MustBegin()
	tx.MustExec(query_insert, sub)
	err = tx.Commit()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to register user"})
		c.Abort()
		return
	}

}
