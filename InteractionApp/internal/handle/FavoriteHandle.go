package handle

import (
	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
)

func GetAllFavorite(c *gin.Context) {
	claims, ok := c.Get("claims")
	sub, err := claims.(jwt.MapClaims).GetSubject()
	if !ok || err != nil {
		c.JSON(401, gin.H{"error": "Unauthorized"})
		c.Abort()
		return
	}
	c.JSON(200, gin.H{"message": "Get all favorites for user " + sub})

}
