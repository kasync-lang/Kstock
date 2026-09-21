package api

import (
	"Kstock/internal/middleware"
	"time"

	"github.com/gin-gonic/gin"
)

func RegisterAllRoutes(routes *gin.Engine) {
	routes.Use(middleware.OWASPSecurityHeaders())
	routes.Use(middleware.RateLimit(100, time.Minute))
	mainRoute := routes.Group("/api")
	RegisterSymbolRoutes(mainRoute)
	RegisterHistoryChartRoutes(mainRoute)

	privateRoute := mainRoute.Group("")
	privateRoute.Use(middleware.AuthMiddleware())
	RegisterFavoriteRoutes(privateRoute)
	RegisterNoteRoutes(privateRoute)
	RegisterAlertRoutes(privateRoute)
	RegisterAssetRoutes(privateRoute)
	RegisterTransactionHandle(privateRoute)
	RegisterSocketRoute(privateRoute)

}
