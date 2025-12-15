package handle

import (
	"Kstock/internal/dto"
	"Kstock/internal/server"
	"log"
	"net/http"

	"github.com/gin-gonic/gin"
)

func GetSymbols(c *gin.Context) {
	// Implementation for getting symbols
	name := c.Query("name")
	exchange := c.DefaultQuery("exchange", "NASDAQ")
	order_by := c.DefaultQuery("order_by", "name")

	db := server.GetDB()
	allowed := map[string]struct{}{
		"name":       {},
		"market_cap": {},
		"ipo":        {},
	}
	if _, ok := allowed[name]; !ok {
		c.AbortWithStatusJSON(http.StatusBadRequest, gin.H{"error": "Invalid order_by parameter"})
		return
	}

	query := `Select name, ticker, logo from company_profile where (name like $1  OR ticker like $1 and exchange like $2 order by $3`
	symbol := dto.SymbolPublic{}
	row, err := db.Queryx(query, name+"%", exchange+"%", order_by)
	if err != nil {
		c.AbortWithStatusJSON(http.StatusInternalServerError, gin.H{"error": "Internal server error"})
		return
	}
	data := []dto.SymbolPublic{}
	for row.Next() {
		err := row.StructScan(&symbol)
		if err != nil {
			log.Fatal(err)
		}
		data = append(data, symbol)
	}
	c.JSON(200, gin.H{"data": data})
}
