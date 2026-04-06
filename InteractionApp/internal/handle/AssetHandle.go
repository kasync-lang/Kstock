package handle

import (
	"Kstock/internal/dto"
	"Kstock/internal/server"
	"log"
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
)

func GetAsset(c *gin.Context) {
	claims, ok := c.Get("claims")
	v, ok := c.Get("price_store")
	ps, ok2 := v.(*dto.PriceStore)
	if !ok || !ok2 {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Internal Server Error"})
		c.Abort()
		log.Printf("Failed to get price store from context")
		return
	}
	sub, err := claims.(jwt.MapClaims).GetSubject()
	if err != nil {
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
	defer rows.Close()
	for rows.Next() {
		var asset dto.Asset
		if err := rows.Scan(&asset.Symbol, &asset.Quantity, &asset.Price); err != nil {
			log.Println(err)
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Internal Server Error"})
			c.Abort()
			return
		}
		value, ok := ps.Get(asset.Symbol)
		if !ok {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "Internal Server Error"})
			c.Abort()
			log.Printf("Price for symbol %s not found in price store", asset.Symbol)
		}
		asset.MarketValue = value
		loss := asset.Quantity * (value - asset.Price)
		asset.ProfitAndLoss = loss
		assets.Data = append(assets.Data, asset)

	}
	var combineProfit float64 = 0
	for _, asset := range assets.Data {
		combineProfit += asset.ProfitAndLoss
	}
	assets.AllProfitAndLoss = combineProfit
	if err := rows.Err(); err != nil {
		log.Println(err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Internal Server Error"})
		c.Abort()
		return
	}
	c.JSON(http.StatusOK, assets)
}
