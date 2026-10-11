package api

import (
	"Kstock/internal/handle"

	"github.com/gin-gonic/gin"
)

func RegisterAlertRoutes(router *gin.RouterGroup) {
	alertGroup := router.Group("/alerts")
	{
		alertGroup.POST("/", handle.CreateAlert)
		alertGroup.GET("/:symbol", handle.GetAlertsBySymbol)
		alertGroup.PUT("/:alert_id", handle.UpdateAlert)
		alertGroup.DELETE("/:alert_id", handle.DeleteAlert)

	}
}
