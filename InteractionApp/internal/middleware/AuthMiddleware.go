package middleware

import (
	"Kstock/internal/server"
	"Kstock/pkg/jwk"
	"errors"
	"net/http"
	"strings"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
)

type AuthErrorResponse struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

var (
	ErrRespMissingToken = AuthErrorResponse{
		Code:    "MISSING_TOKEN",
		Message: "Bearer token is required",
	}
	ErrRespInvalidToken = AuthErrorResponse{
		Code:    "INVALID_TOKEN",
		Message: "Token is invalid",
	}
	ErrRespTokenExpired = AuthErrorResponse{
		Code:    "ACCESS_TOKEN_EXPIRED",
		Message: "Access token has expired",
	}
)

func abortWithAuthError(c *gin.Context, resp AuthErrorResponse) {
	c.JSON(http.StatusUnauthorized, resp)
	c.Abort()
}

func abortWithVerifyError(c *gin.Context, err error) {
	if errors.Is(err, jwt.ErrTokenExpired) {
		abortWithAuthError(c, ErrRespTokenExpired)
		return
	}
	abortWithAuthError(c, ErrRespInvalidToken)
}

func AuthMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		authHeader := strings.TrimSpace(c.Request.Header.Get("Authorization"))
		if authHeader == "" {
			abortWithAuthError(c, ErrRespMissingToken)
			return
		}
		bearerToken := strings.Split(authHeader, " ")
		if len(bearerToken) != 2 || bearerToken[0] != "Bearer" || bearerToken[1] == "" {
			abortWithAuthError(c, ErrRespMissingToken)
			return
		}
		tokenStr := bearerToken[1]

		claims, err := jwk.Verify(tokenStr)
		if err != nil {
			abortWithVerifyError(c, err)
			return
		}

		TemporaryRegiterUser(claims, c)
		if c.IsAborted() {
			return
		}
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
	query_insert := `insert into user_table (id) values ($1) on conflict (id) do nothing`
	tx := db.MustBegin()
	tx.MustExec(query_insert, sub)
	err = tx.Commit()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to register user"})
		c.Abort()
		return
	}

}

func AuthSocketMiddleware() gin.HandlerFunc {
	return func(c *gin.Context) {
		tokenStr := c.Query("token")
		if tokenStr == "" {
			authHeader := strings.TrimSpace(c.Request.Header.Get("Authorization"))
			if authHeader == "" {
				abortWithAuthError(c, ErrRespMissingToken)
				return
			}
			parts := strings.Split(authHeader, " ")
			if len(parts) != 2 || parts[0] != "Bearer" || parts[1] == "" {
				abortWithAuthError(c, ErrRespMissingToken)
				return
			}
			tokenStr = parts[1]
		}
		claims, err := jwk.Verify(tokenStr)
		if err != nil {
			abortWithVerifyError(c, err)
			return
		}
		c.Set("claims", claims)
		c.Next()
	}
}
