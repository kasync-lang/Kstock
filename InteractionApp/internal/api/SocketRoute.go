package api

import "github.com/gin-gonic/gin"
import "Kstock/internal/handle"

func RegisterSocketRoute(router *gin.RouterGroup) {
	router.Handle("GET", "/ws", handle.UpgradeSocketStreamHandle)
}
