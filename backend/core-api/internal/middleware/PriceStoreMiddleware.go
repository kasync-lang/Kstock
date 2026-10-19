package middleware

import (
	"Kstock/internal/dto"

	"github.com/gin-gonic/gin"
)

func InjectPriceStore(ps *dto.PriceStore) gin.HandlerFunc {
	return func(c *gin.Context) {
		c.Set("price_store", ps)
		c.Next()
	}
}
