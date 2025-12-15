package api
import (
	"github.com/gin-gonic/gin"
	"Kstock/internal/handle"
)

func RegisterSymbolRoutes(router *gin.RouterGroup){
	symbolGroup := router.Group("/symbols")
	{
		symbolGroup.GET("/", handle.GetSymbols)
		
	}
}