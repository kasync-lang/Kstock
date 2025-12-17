package api

import (
	"Kstock/internal/handle"
	"Kstock/internal/middleware"

	"github.com/gin-gonic/gin"
)

func RegisterFavoriteRoutes(router *gin.RouterGroup) {
	favoriteGroup := router.Group("/favorites")
	favoriteGroup.Use(middleware.AuthMiddleware())

	{
		favoriteGroup.GET("", handle.GetAllFavorite)

	}
}
