package handle

import (
	"Kstock/internal/dto"
	"Kstock/internal/server"
	"database/sql"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
	"github.com/jmoiron/sqlx"

	"log"
	"net/http"
	"strings"
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
	if err := c.ShouldBind(&order_data); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Bad Request"})
		log.Printf("Error binding order data: %v", err)
		c.Abort()
		return
	}

	operation := strings.ToUpper(order_data.Operation)
	db := server.GetDB()

	switch operation {
	case "BUY":
		BuyTransactionHandle(db, sub, order_data.Quantity, order_data.Symbol, 100.5, c)
	case "SELL":
		SellTransactionHandle(db, sub, order_data.Quantity, order_data.Symbol, 100.5, c)
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

	// Get current USD balance
	var usd_balance float64
	err = tx.Get(&usd_balance, `SELECT COALESCE(quantity, 0) FROM assets WHERE user_id = $1 AND symbol = 'USD'`, user_id)
	if err != nil && err != sql.ErrNoRows {
		rollbackTx(tx)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to get USD balance"})
		log.Printf("Failed to get USD balance: %v", err)
		c.Abort()
		return
	}

	// Calculate required balance
	required_balance := float64(amount) * price
	dataBuyResponse.TotalCost = required_balance
	// Check if user has enough balance
	if usd_balance < required_balance {
		rollbackTx(tx)
		c.JSON(http.StatusForbidden, gin.H{"error": "Insufficient balance"})
		c.Abort()
		return
	}

	// Get current symbol holdings and unit price
	var old_symbol_amount int
	var old_unit_price float64
	err = tx.Get(&old_symbol_amount, `SELECT COALESCE(quantity, 0) FROM assets WHERE user_id = $1 AND symbol = $2`, user_id, symbol)
	if err != nil && err != sql.ErrNoRows {
		rollbackTx(tx)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to get symbol holdings"})
		log.Printf("Failed to get symbol holdings: %v", err)
		c.Abort()
		return
	}

	err = tx.Get(&old_unit_price, `SELECT COALESCE(unit_price, 0) FROM assets WHERE user_id = $1 AND symbol = $2`, user_id, symbol)
	if err != nil && err != sql.ErrNoRows {
		rollbackTx(tx)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to get unit price"})
		log.Printf("Failed to get unit price: %v", err)
		c.Abort()
		return
	}

	// Calculate new holdings and average unit price
	new_symbol_amount := amount + old_symbol_amount
	new_unit_price := (float64(old_symbol_amount)*old_unit_price + float64(amount)*price) / float64(new_symbol_amount)
	new_usd_balance := usd_balance - required_balance
	dataBuyResponse.TotalHoldings = new_symbol_amount
	// Update USD balance
	_, err = tx.Exec(`UPDATE assets SET quantity = $1 WHERE user_id = $2 AND symbol = 'USD'`, new_usd_balance, user_id)
	if err != nil {
		rollbackTx(tx)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to update USD balance"})
		log.Printf("Failed to update USD balance: %v", err)
		c.Abort()
		return
	}
	dataBuyResponse.NewUsdBalance = new_usd_balance

	// Upsert symbol holdings
	_, err = tx.Exec(`
		INSERT INTO assets (user_id, symbol, quantity, unit_price) 
		VALUES ($1, $2, $3, $4) 
		ON CONFLICT (user_id, symbol) 
		DO UPDATE SET quantity = EXCLUDED.quantity, unit_price = EXCLUDED.unit_price
	`, user_id, symbol, new_symbol_amount, new_unit_price)
	if err != nil {
		rollbackTx(tx)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to update symbol holdings"})
		log.Printf("Failed to update symbol holdings: %v", err)
		c.Abort()
		return
	}
	dataBuyResponse.NewUnitPrice = new_unit_price

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

	// Get current symbol holdings
	var current_symbol_amount int
	err = tx.Get(&current_symbol_amount, `SELECT COALESCE(quantity, 0) FROM assets WHERE user_id = $1 AND symbol = $2`, user_id, symbol)
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

	// Get current USD balance
	var usd_balance float64
	err = tx.Get(&usd_balance, `SELECT COALESCE(quantity, 0) FROM assets WHERE user_id = $1 AND symbol = 'USD'`, user_id)
	if err != nil && err != sql.ErrNoRows {
		rollbackTx(tx)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to get USD balance"})
		log.Printf("Failed to get USD balance: %v", err)
		c.Abort()
		return
	}

	// Calculate new balances
	sale_proceeds := float64(amount) * price
	new_symbol_amount := current_symbol_amount - amount
	new_usd_balance := usd_balance + sale_proceeds

	// Update USD balance
	_, err = tx.Exec(`UPDATE assets SET quantity = $1 WHERE user_id = $2 AND symbol = 'USD'`, new_usd_balance, user_id)
	if err != nil {
		rollbackTx(tx)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Failed to update USD balance"})
		log.Printf("Failed to update USD balance: %v", err)
		c.Abort()
		return
	}
	dataSellResponse.TotalProceeds = sale_proceeds

	// Update or delete symbol holdings
	if new_symbol_amount > 0 {
		_, err = tx.Exec(`UPDATE assets SET quantity = $1 WHERE user_id = $2 AND symbol = $3`, new_symbol_amount, user_id, symbol)
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
	dataSellResponse.NewUsdBalance = new_usd_balance
	dataSellResponse.RemainingHoldings = new_symbol_amount

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
	dataSellResponse.Message = "BUY transaction successful"

	c.JSON(http.StatusOK, dataSellResponse)
	log.Printf("SELL transaction completed: user=%s, symbol=%s, amount=%d, price=%.2f", user_id, symbol, amount, price)
}
