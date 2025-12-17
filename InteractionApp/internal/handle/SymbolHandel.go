package handle

import (
	"Kstock/internal/dto"
	"Kstock/internal/server"
	"fmt"
	"log"
	"net/http"

	"github.com/gin-gonic/gin"
)

func GetSymbols(c *gin.Context) {
	// Implementation for getting symbols
	var query_symbol dto.QuerySymbol
	db := server.GetDB()
	log.Println(db)

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
	log.Printf("query_symbol: %v", query_symbol)
	query := fmt.Sprintf(`
SELECT name, ticker, logo
FROM company_profile
WHERE (name LIKE $1 OR ticker LIKE $1)
  AND exchange LIKE $2
ORDER BY %s
`, orderBy)
	symbol := dto.SymbolPublic{}
	row, err := db.Queryx(query, query_symbol.Name+"%", query_symbol.Exhange+"%")
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": "Internal server error"})
		return
	}
	var data []dto.SymbolPublic

	for row.Next() {
		err := row.StructScan(&symbol)
		if err != nil {
			log.Fatal(err)
		}
		log.Println(symbol)
		data = append(data, symbol)
	}
	log.Println(data)
	c.JSON(200, gin.H{"data": data})
}
func GetSymbolDetail(c *gin.Context) {
	symbol := c.Param("symbol")
	db := server.GetDB()
	log.Println(db)
	symbolDetail := dto.SymbolBaseDetail{}
	err := db.Get(&symbolDetail, `SELECT * FROM company_profile WHERE ticker=$1`, symbol)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": "Internal server error"})
		return
	}
	c.JSON(200, gin.H{"data": symbolDetail})
}
