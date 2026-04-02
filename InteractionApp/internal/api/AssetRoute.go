package api

import (
	"Kstock/internal/handle"

	"github.com/gin-gonic/gin"
)

func RegisterAssetRoutes(router *gin.RouterGroup) {
	assetGroup := router.Group("/assets")
	{
		assetGroup.GET("/", handle.GetAsset)
	}
}
