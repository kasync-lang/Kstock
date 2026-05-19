package handle

import (
	"Kstock/internal/server"
	"log"

	"github.com/gin-gonic/gin"
)

func UpgradeSocketStreamHandle(c *gin.Context) {
	log.Println("UpgradeSocketStreamHandle")
	server.GetManager().ServeWS(c.Writer, c.Request)
}
