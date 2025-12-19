package api

import (
	"Kstock/internal/handle"

	"github.com/gin-gonic/gin"
)

func RegisterNoteRoutes(router *gin.RouterGroup) {
	noteGroup := router.Group("/notes")
	{
		noteGroup.GET("/", handle.GetAllNotes)
		noteGroup.POST("/", handle.CreateNote)
		noteGroup.GET("/:symbol", handle.GetNoteBySymbol)
		noteGroup.PUT("/", handle.UpdateNote)
		noteGroup.DELETE("/:note_id", handle.DeleteNote)
		
	}
}
