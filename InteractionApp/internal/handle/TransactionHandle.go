package handle

import (
	"Kstock/internal/dto"
	"Kstock/internal/server"
	"database/sql"
	"log"
	"math"
	"net/http"
	"strconv"
	"strings"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
	"github.com/jmoiron/sqlx"
)

func TransactionHandle(c *gin.Context) {
	claims, ok := c.Get("claims")
	if !ok {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized"})
		c.Abort()
		return
	}

	sub, err := claims.(jwt.MapClaims).GetSubject()
	if err != nil {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized"})
		c.Abort()
		return
	}

	var order_data dto.Order
	if err := c.ShouldBindJSON(&order_data); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Bad Request"})
		log.Printf("Error binding order data: %v", err)
		c.Abort()
		return
	}

	order_data.Symbol = strings.ToUpper(strings.TrimSpace(order_data.Symbol))
	if order_data.Quantity <= 0 || order_data.Symbol == "" || order_data.Symbol == "USD" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "quantity must be positive and symbol must be a tradable stock"})
		c.Abort()
		return
	}

	operation := strings.ToUpper(order_data.Operation)
	db := server.GetDB()
	v, ok := c.Get("price_store")
	ps, ok2 := v.(*dto.PriceStore)
	if !ok2 || !ok {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized"})
		c.Abort()
		return
	}
	priceToProcess, ok := ps.Get(order_data.Symbol)
	if !ok || priceToProcess <= 0 || math.IsNaN(priceToProcess) || math.IsInf(priceToProcess, 0) {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Internal Server Error"})
		log.Printf("Price not found for order: %+v", order_data)
		c.Abort()
		return
	}
	switch operation {
	case "BUY":
		BuyTransactionHandle(db, sub, order_data.Quantity, order_data.Symbol, priceToProcess, c)
	case "SELL":
		SellTransactionHandle(db, sub, order_data.Quantity, order_data.Symbol, priceToProcess, c)
	default:
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid operation"})
		c.Abort()
	}
}

// Helper function to safely rollback transaction
func rollbackTx(tx *sqlx.Tx) {
	if err := tx.Rollback(); err != nil && err != sql.ErrTxDone {
		log.Printf("Failed to rollback transaction: %v", err)
	}
}

// lockCashBalance creates an empty cash balance when necessary, then locks the
// user's row until the enclosing transaction completes. This prevents two orders
// from spending the same balance concurrently.
func lockCashBalance(tx *sqlx.Tx, userID string) (float64, error) {
	if _, err := tx.Exec(`INSERT INTO cash (user_id, amount) VALUES ($1, 0) ON CONFLICT (user_id) DO NOTHING`, userID); err != nil {
		return 0, err
	}

	var balance float64
	err := tx.Get(&balance, `SELECT COALESCE(amount, 0) FROM cash WHERE user_id = $1 FOR UPDATE`, userID)
	return balance, err
}

func roundCurrency(amount float64) float64 {
	return math.Round(amount*100) / 100
}

func BuyTransactionHandle(db *sqlx.DB, user_id string, amount int, symbol string, price float64, c *gin.Context) {
	// Start transaction
	tx, err := db.Beginx()
	var dataBuyResponse dto.BuyOrderResponse
	dataBuyResponse.Symbol = symbol
	dataBuyResponse.Amount = amount
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to start transaction"})
		log.Printf("Failed to begin transaction: %v", err)
		c.Abort()
		return
	}

	// Create and lock the dedicated cash row before checking the available balance.
	cashBalance, err := lockCashBalance(tx, user_id)
	if err != nil {
		rollbackTx(tx)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to get cash balance"})
		log.Printf("Failed to get cash balance: %v", err)
		c.Abort()
		return
	}

	// Calculate required balance
	requiredBalance := roundCurrency(float64(amount) * price)
	dataBuyResponse.TotalCost = requiredBalance
	// Check if user has enough balance
	if cashBalance < requiredBalance {
		rollbackTx(tx)
		c.JSON(http.StatusForbidden, gin.H{"error": "Insufficient balance"})
		c.Abort()
		return
	}

	// Lock the holding row while recalculating its quantity and average price.
	var old_symbol_amount int
	var old_unit_price float64
	err = tx.QueryRowx(`SELECT quantity, average_price FROM assets WHERE user_id = $1 AND symbol = $2 FOR UPDATE`, user_id, symbol).Scan(&old_symbol_amount, &old_unit_price)
	if err != nil && err != sql.ErrNoRows {
		rollbackTx(tx)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to get symbol holdings"})
		log.Printf("Failed to get symbol holdings: %v", err)
		c.Abort()
		return
	}

	if err == sql.ErrNoRows {
		old_symbol_amount = 0
		old_unit_price = 0
	}

	// Calculate new holdings and average unit price
	newSymbolAmount := amount + old_symbol_amount
	newUnitPrice := (float64(old_symbol_amount)*old_unit_price + float64(amount)*price) / float64(newSymbolAmount)
	newCashBalance := cashBalance - requiredBalance
	dataBuyResponse.TotalHoldings = newSymbolAmount
	// Update cash balance
	_, err = tx.Exec(`UPDATE cash SET amount = $1 WHERE user_id = $2`, newCashBalance, user_id)
	if err != nil {
		rollbackTx(tx)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to update cash balance"})
		log.Printf("Failed to update cash balance: %v", err)
		c.Abort()
		return
	}
	dataBuyResponse.NewCashBalance = newCashBalance

	// Upsert symbol holdings
	_, err = tx.Exec(`
		INSERT INTO assets (user_id, symbol, quantity, average_price)
		VALUES ($1, $2, $3, $4) 
		ON CONFLICT (user_id, symbol) 
		DO UPDATE SET quantity = EXCLUDED.quantity, average_price = EXCLUDED.average_price
	`, user_id, symbol, newSymbolAmount, newUnitPrice)
	if err != nil {
		rollbackTx(tx)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to update symbol holdings"})
		log.Printf("Failed to update symbol holdings: %v", err)
		c.Abort()
		return
	}
	dataBuyResponse.NewUnitPrice = newUnitPrice

	// Insert transaction history
	_, err = tx.Exec(`
		INSERT INTO transaction (user_id, amount, symbol, operation, price) 
		VALUES ($1, $2, $3, $4, $5)
	`, user_id, amount, symbol, "BUY", price)
	if err != nil {
		rollbackTx(tx)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to record transaction"})
		log.Printf("Failed to record transaction: %v", err)
		c.Abort()
		return
	}

	// Commit transaction
	err = tx.Commit()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to commit transaction"})
		log.Printf("Failed to commit transaction: %v", err)
		c.Abort()
		return
	}
	dataBuyResponse.Message = "BUY transaction successful"

	c.JSON(http.StatusOK, dataBuyResponse)
	log.Printf("BUY transaction completed: user=%s, symbol=%s, amount=%d, price=%.2f", user_id, symbol, amount, price)
}

func SellTransactionHandle(db *sqlx.DB, user_id string, amount int, symbol string, price float64, c *gin.Context) {
	// Start transaction
	tx, err := db.Beginx()
	var dataSellResponse dto.SellOrderResponse
	dataSellResponse.Symbol = symbol
	dataSellResponse.Amount = amount
	dataSellResponse.Price = price
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to start transaction"})
		log.Printf("Failed to begin transaction: %v", err)
		c.Abort()
		return
	}

	// Lock the holding row before validating and reducing it.
	var current_symbol_amount int
	err = tx.Get(&current_symbol_amount, `SELECT quantity FROM assets WHERE user_id = $1 AND symbol = $2 FOR UPDATE`, user_id, symbol)
	if err != nil && err != sql.ErrNoRows {
		rollbackTx(tx)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to get symbol holdings"})
		log.Printf("Failed to get symbol holdings: %v", err)
		c.Abort()
		return
	}

	// Check if user has enough symbol to sell
	if current_symbol_amount < amount {
		rollbackTx(tx)
		c.JSON(http.StatusForbidden, gin.H{"error": "Insufficient holdings"})
		c.Abort()
		return
	}

	// Lock or create the dedicated cash row before crediting sale proceeds.
	cashBalance, err := lockCashBalance(tx, user_id)
	if err != nil {
		rollbackTx(tx)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to get cash balance"})
		log.Printf("Failed to get cash balance: %v", err)
		c.Abort()
		return
	}

	// Calculate new balances
	saleProceeds := roundCurrency(float64(amount) * price)
	newSymbolAmount := current_symbol_amount - amount
	newCashBalance := cashBalance + saleProceeds

	// Update cash balance
	_, err = tx.Exec(`UPDATE cash SET amount = $1 WHERE user_id = $2`, newCashBalance, user_id)
	if err != nil {
		rollbackTx(tx)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to update cash balance"})
		log.Printf("Failed to update cash balance: %v", err)
		c.Abort()
		return
	}
	dataSellResponse.TotalProceeds = saleProceeds

	// Update or delete symbol holdings
	if newSymbolAmount > 0 {
		_, err = tx.Exec(`UPDATE assets SET quantity = $1 WHERE user_id = $2 AND symbol = $3`, newSymbolAmount, user_id, symbol)
	} else {
		_, err = tx.Exec(`DELETE FROM assets WHERE user_id = $1 AND symbol = $2`, user_id, symbol)
	}

	if err != nil {
		rollbackTx(tx)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to update symbol holdings"})
		log.Printf("Failed to update symbol holdings: %v", err)
		c.Abort()
		return
	}
	dataSellResponse.NewCashBalance = newCashBalance
	dataSellResponse.RemainingHoldings = newSymbolAmount

	// Insert transaction history
	_, err = tx.Exec(`
		INSERT INTO transaction (user_id, amount, symbol, operation, price) 
		VALUES ($1, $2, $3, $4, $5)
	`, user_id, amount, symbol, "SELL", price)
	if err != nil {
		rollbackTx(tx)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to record transaction"})
		log.Printf("Failed to record transaction: %v", err)
		c.Abort()
		return
	}

	// Commit transaction
	err = tx.Commit()
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to commit transaction"})
		log.Printf("Failed to commit transaction: %v", err)
		c.Abort()
		return
	}
	dataSellResponse.Message = "SELL transaction successful"

	c.JSON(http.StatusOK, dataSellResponse)
	log.Printf("SELL transaction completed: user=%s, symbol=%s, amount=%d, price=%.2f", user_id, symbol, amount, price)
}

func TransactionHistoryHandle(c *gin.Context) {
	const pageSize = 50

	claims, ok := c.Get("claims")
	if !ok {
		c.JSON(http.StatusUnauthorized, gin.H{"error": "Unauthorized"})
		c.Abort()
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

	page := 1
	if pageQuery := c.Query("page"); pageQuery != "" {
		page, err = strconv.Atoi(pageQuery)
		if err != nil || page < 1 {
			c.JSON(http.StatusBadRequest, gin.H{
				"error": "page must be a positive integer",
			})
			c.Abort()
			return
		}
	}

	db := server.GetDB()

	var total int
	err = db.Get(
		&total,
		`SELECT COUNT(*) FROM transaction WHERE user_id = $1`,
		sub,
	)
	if err != nil {
		log.Printf("Failed to count transaction history for user %s: %v", sub, err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to retrieve transaction history",
		})
		c.Abort()
		return
	}

	offset := (page - 1) * pageSize
	history := make([]dto.TransactionHistoryItem, 0)

	err = db.Select(
		&history,
		`
		SELECT id, amount, symbol, operation, price, time_transacted
		FROM transaction
		WHERE user_id = $1
		ORDER BY time_transacted DESC, id DESC
		LIMIT $2 OFFSET $3
		`,
		sub,
		pageSize,
		offset,
	)
	if err != nil {
		log.Printf("Failed to retrieve transaction history for user %s: %v", sub, err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"error": "Failed to retrieve transaction history",
		})
		c.Abort()
		return
	}

	totalPages := (total + pageSize - 1) / pageSize

	c.JSON(http.StatusOK, dto.TransactionHistoryResponse{
		Data:       history,
		Page:       page,
		PageSize:   pageSize,
		Total:      total,
		TotalPages: totalPages,
		HasNext:    page < totalPages,
	})
}
