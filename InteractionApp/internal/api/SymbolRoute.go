package api

import (
	"Kstock/internal/handle"

	"github.com/gin-gonic/gin"
)

func RegisterSymbolRoutes(router *gin.RouterGroup) {
	symbolGroup := router.Group("/symbols")

	{
		symbolGroup.GET("", handle.GetSymbols)
		symbolGroup.GET("/:symbol/detail", handle.GetSymbolDetail)

	}
}
