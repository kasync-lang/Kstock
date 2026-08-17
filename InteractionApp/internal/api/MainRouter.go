package api

import (
	"Kstock/internal/middleware"
	"time"

	"github.com/gin-gonic/gin"
)

func RegisterAllRoutes(routes *gin.Engine) {
	routes.Use(middleware.OWASPSecurityHeaders())
	routes.Use(middleware.RateLimit(100, time.Minute))
	//routes.Use(middleware.AuthMiddleware())
	main_route := routes.Group("/api")
	RegisterSymbolRoutes(main_route)
	RegisterFavoriteRoutes(main_route)
	RegisterNoteRoutes(main_route)
	RegisterAlertRoutes(main_route)
	RegisterAssetRoutes(main_route)
	RegisterTransactionHandle(main_route)
	RegisterSocketRoute(main_route)
	RegisterHistoryChartRoutes(main_route)

}
