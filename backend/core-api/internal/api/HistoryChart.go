package api

import (
	"Kstock/internal/handle"

	"github.com/gin-gonic/gin"
)

func RegisterHistoryChartRoutes(router *gin.RouterGroup) {
	router.GET("/chart/history", handle.GetHistoryChart)
}
