package handle

import (
	"Kstock/internal/dto"
	"Kstock/internal/server"
	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
	"log"
	"net/http"
)

func GetAsset(c *gin.Context) {
	claims, ok := c.Get("claims")
	sub, err := claims.(jwt.MapClaims).GetSubject()
	if !ok || err != nil {
		c.JSON(401, gin.H{"error": "Unauthorized"})
		c.Abort()
		return
	}
	db := server.GetDB()
	assets := dto.Assets{}
	query_get_assets := `select symbol, quantity, unit_price from assets where user_id = $1`
	rows, err2 := db.Queryx(query_get_assets, sub)
	if err2 != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Internal Server Error"})
		log.Printf("Error getting assets: %v", err2)
		c.Abort()
		return

	}
	log.Printf("hehe")
	defer rows.Close()
	for rows.Next() {
		var asset dto.Asset
		if err := rows.Scan(&asset.Symbol, &asset.Quantity, &asset.Price); err != nil {
			log.Println(err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Internal Server Error"})
			c.Abort()
			return
		}
		assets.Data = append(assets.Data, asset)

	}
	if err := rows.Err(); err != nil {
		log.Println(err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Internal Server Error"})
		c.Abort()
		return
	}
	c.JSON(http.StatusOK, assets)
}
