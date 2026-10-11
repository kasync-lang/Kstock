package handle

import (
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
		"market_cap": "market_capitalization",
		"ipo":        "ipo",
	}
	orderBy, ok := allowedOrderBy[query_symbol.OrderBy]
	if !ok {
		orderBy = "ticker"
	}
	args := []interface{}{strings.ToUpper(query_symbol.Name) + "%", query_symbol.Exhange + "%"}
	limitClause := ""
	if query_symbol.Limit > 0 {
		limitClause = " LIMIT $3 OFFSET $4"
		args = append(args, query_symbol.Limit, query_symbol.Offset)
	}
	query := fmt.Sprintf(`
SELECT name, ticker, logo
FROM company_profile
WHERE (name LIKE $1 OR ticker LIKE $1)
  AND exchange LIKE $2
ORDER BY %s%s
`, orderBy, limitClause)
	row, err := db.Queryx(query, args...)
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

	dailyStore := server.GetDailyCloseStore()
	var priceStore *dto.PriceStore
	if v, ok := c.Get("price_store"); ok {
		if ps, okCast := v.(*dto.PriceStore); okCast {
			priceStore = ps
		}
	}

	// Warm cache on demand if not loaded yet (e.g. cold start) and ClickHouse is available
	if (dailyStore == nil || dailyStore.Len() == 0) && conn_click_house != nil {
		if err := server.LoadDailyCloses(c.Request.Context(), conn_click_house, dailyStore); err != nil {
			log.Printf("fallback load daily close cache: %v", err)
		}
	}

	for i := range data {
		ticker := data[i].Ticker
		if dailyStore != nil {
			if dc, ok := dailyStore.Get(ticker); ok {
				if dc.HasLast {
					data[i].LastPrice = dc.Last
				}
				if dc.HasPrev && dc.Prev != 0 {
					data[i].PercentChange = (dc.Last - dc.Prev) / dc.Prev * 100
				}
			}
		}

		if priceStore != nil {
			if livePrice, ok := priceStore.Get(ticker); ok && livePrice > 0 {
				data[i].LastPrice = livePrice
				if dailyStore != nil {
					if dc, ok := dailyStore.Get(ticker); ok && dc.HasPrev && dc.Prev != 0 {
						data[i].PercentChange = (livePrice - dc.Prev) / dc.Prev * 100
					}
				}
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
