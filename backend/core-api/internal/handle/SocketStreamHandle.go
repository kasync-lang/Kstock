package handle

import (
	"Kstock/internal/server"

	"github.com/gin-gonic/gin"
)

func UpgradeSocketStreamHandle(c *gin.Context) {
	server.GetManager().ServeWS(c.Writer, c.Request)
}
