package api

import (
	"Kstock/internal/handle"

	"github.com/gin-gonic/gin"
)

func RegisterFavoriteRoutes(router *gin.RouterGroup) {
	favoriteGroup := router.Group("/favorites")

	{
		favoriteGroup.GET("", handle.GetAllFavorite)
		favoriteGroup.POST("/:symbol", handle.AddFavorite)
		favoriteGroup.DELETE("/:symbol", handle.RemoveFavorite)

	}
}
