package handle

import (
	"Kstock/internal/dto"
	"Kstock/internal/server"
	"database/sql"
	"log"
	"math"
	"net/http"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
)

func GetAsset(c *gin.Context) {
	claims, ok := c.Get("claims")
	v, _ := c.Get("price_store")
	ps, ok2 := v.(*dto.PriceStore)
	if !ok {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized"})
		c.Abort()
		return
	}
	if !ok2 {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Internal Server Error"})
		c.Abort()
		log.Printf("Failed to get price store from context")
		return
	}
	mapClaims, ok := claims.(jwt.MapClaims)
	if !ok {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized"})
		c.Abort()
		return
	}
	sub, err := mapClaims.GetSubject()
	if err != nil || sub == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized"})
		c.Abort()
		return
	}
	db := server.GetDB()
	assets := dto.Assets{}
	queryGetAssets := `SELECT symbol, quantity, average_price FROM assets WHERE user_id = $1`
	rows, err2 := db.Queryx(queryGetAssets, sub)
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
			return
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

	// Fetch cash balance from dedicated cash table
	var cashBalance float64
	err = db.Get(&cashBalance, `SELECT COALESCE(amount, 0) FROM cash WHERE user_id = $1`, sub)
	if err != nil && err != sql.ErrNoRows {
		log.Printf("Error getting cash balance: %v", err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Internal Server Error"})
		c.Abort()
		return
	}
	assets.CashBalance = cashBalance

	c.JSON(http.StatusOK, assets)
}

// GetCashBalance returns the authenticated user's available USD balance.
func GetCashBalance(c *gin.Context) {
	claims, ok := c.Get("claims")
	if !ok {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized"})
		return
	}

	mapClaims, ok := claims.(jwt.MapClaims)
	if !ok {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized"})
		return
	}

	userID, err := mapClaims.GetSubject()
	if err != nil || userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized"})
		return
	}

	var cashBalance float64
	err = server.GetDB().Get(&cashBalance, `SELECT COALESCE(amount, 0) FROM cash WHERE user_id = $1`, userID)
	if err != nil && err != sql.ErrNoRows {
		log.Printf("Error getting cash balance for user %s: %v", userID, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Internal Server Error"})
		return
	}

	c.JSON(http.StatusOK, dto.CashBalanceResponse{CashBalance: cashBalance})
}

func Topup(c *gin.Context) {
	claims, ok := c.Get("claims")
	if !ok {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized"})
		return
	}

	mapClaims, ok := claims.(jwt.MapClaims)
	if !ok {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized"})
		return
	}

	userID, err := mapClaims.GetSubject()
	if err != nil || userID == "" {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized"})
		return
	}

	var request dto.TopupRequest
	if err := c.ShouldBindJSON(&request); err != nil || math.IsNaN(request.Amount) || math.IsInf(request.Amount, 0) {
		c.JSON(http.StatusBadRequest, gin.H{"error": "amount must be a positive USD value"})
		return
	}

	var newBalance float64
	err = server.GetDB().Get(&newBalance, `
		INSERT INTO cash (user_id, amount)
		VALUES ($1, $2)
		ON CONFLICT (user_id)
		DO UPDATE SET amount = cash.amount + EXCLUDED.amount
		RETURNING amount
	`, userID, request.Amount)
	if err != nil {
		log.Printf("Failed to top up cash balance for user %s: %v", userID, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to top up balance"})
		return
	}

	c.JSON(http.StatusOK, dto.TopupResponse{
		Message:        "Top-up successful",
		Amount:         request.Amount,
		NewCashBalance: newBalance,
	})
}
