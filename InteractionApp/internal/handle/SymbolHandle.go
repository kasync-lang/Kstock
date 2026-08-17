package handle

import (
	"Kstock/internal/config"
	"Kstock/internal/dto"
	"Kstock/internal/server"
	"fmt"
	"log"
	"net/http"
	"strings"

	"github.com/gin-gonic/gin"
)

func GetSymbols(c *gin.Context) {
	// Implementation for getting symbols
	var query_symbol dto.QuerySymbol
	db := server.GetDB()
	conn_click_house := server.GetClickHouse()
	if err := c.ShouldBindQuery(&query_symbol); err != nil {
		c.AbortWithStatusJSON(http.StatusBadRequest, gin.H{"error": "Invalid query parameters"})
		return
	}
	allowedOrderBy := map[string]string{
		"name":       "name",
		"market_cap": "market_cap",
		"ipo":        "ipo",
	}
	orderBy, ok := allowedOrderBy[query_symbol.OrderBy]
	if !ok {
		orderBy = "ticker"
	}
	query := fmt.Sprintf(`
SELECT name, ticker, logo
FROM company_profile
WHERE (name LIKE $1 OR ticker LIKE $1)
  AND exchange LIKE $2
ORDER BY %s
`, orderBy)
	row, err := db.Queryx(query, strings.ToUpper(query_symbol.Name)+"%", query_symbol.Exhange+"%")
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": "Internal server error"})
		return
	}
	defer func() { _ = row.Close() }()

	data := make([]dto.SymbolPreview, 0)
	for row.Next() {
		var symbol dto.SymbolPublic
		if err := row.StructScan(&symbol); err != nil {
			log.Printf("scan symbol: %v", err)
			c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": "Internal server error"})
			return
		}
		data = append(data, dto.SymbolPreview{SymbolPublic: symbol})
	}
	if err := row.Err(); err != nil {
		log.Printf("iterate symbols: %v", err)
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": "Internal server error"})
		return
	}

	if conn_click_house != nil && config.Cfg != nil {
		priceQuery := fmt.Sprintf(`SELECT close FROM %s.ohlcv_1d WHERE symbol = ? ORDER BY timestamp DESC LIMIT 2`, config.Cfg.ClickHouseDatabase)
		for i := range data {
			rows, err := conn_click_house.Query(c.Request.Context(), priceQuery, data[i].Ticker)
			if err != nil {
				log.Printf("get price history for %s: %v", data[i].Ticker, err)
				continue
			}

			prices := make([]float64, 0, 2)
			for rows.Next() {
				var price float64
				if err := rows.Scan(&price); err != nil {
					log.Printf("scan price history for %s: %v", data[i].Ticker, err)
					continue
				}
				prices = append(prices, price)
			}
			if err := rows.Err(); err != nil {
				log.Printf("iterate price history for %s: %v", data[i].Ticker, err)
			}
			_ = rows.Close()

			if len(prices) > 0 {
				data[i].LastPrice = prices[0]
			}
			if len(prices) > 1 && prices[1] != 0 {
				data[i].PercentChange = (prices[0] - prices[1]) / prices[1] * 100
			}
		}
	}

	c.JSON(http.StatusOK, gin.H{"data": data})
}
func GetSymbolDetail(c *gin.Context) {
	symbol := c.Param("symbol")
	db := server.GetDB()
	log.Println(db)
	symbolDetail := dto.SymbolBaseDetail{}
	err := db.Get(&symbolDetail, `SELECT * FROM company_profile WHERE ticker=$1`, strings.ToUpper(symbol))
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": "Internal server error"})
		return
	}
	c.JSON(200, gin.H{"data": symbolDetail})
}
