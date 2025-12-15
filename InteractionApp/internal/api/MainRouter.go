package api

import (
	"github.com/gin-gonic/gin"
	"Kstock/internal/middleware"
	"time"
)
func RegisterAllRoutes(routes *gin.Engine) {
	routes.Use(middleware.OWASPSecurityHeaders())
	routes.Use(middleware.RateLimit(100, time.Minute))
	//routes.Use(middleware.AuthMiddleware())
	main_route := routes.Group("/api/v1")
	RegisterSymbolRoutes(main_route)
}