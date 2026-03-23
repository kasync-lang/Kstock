package handle

import (
	"Kstock/internal/dto"
	"Kstock/internal/server"
	"log"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
)

func CreateNote(c *gin.Context) {
	var data_create dto.NoteCreate
	claims, ok := c.Get("claims")
	sub, err := claims.(jwt.MapClaims).GetSubject()
	if !ok || err != nil {
		c.JSON(401, gin.H{"error": "Unauthorized"})
		c.Abort()
		return
	}
	if errA := c.ShouldBind(&data_create); errA != nil {
		c.JSON(400, gin.H{"error": errA.Error()})
		c.Abort()
		return
	}

	db := server.GetDB()
	var note dto.NotePublic
	query_create_note := `insert into note (user_id, symbol,title, content) values ($1, $2, $3, $4) returning note_id, title`
	err2 := db.Get(&note, query_create_note, sub, data_create.Symbol, data_create.Title, data_create.Content)
	if err2 != nil {
		c.JSON(500, gin.H{"error": "Internal Server Error"})
		log.Printf("Error creating note: %v", err2)
		c.Abort()
		return
	}
	c.JSON(200, gin.H{"data": note})
}
func GetAllNotes(c *gin.Context) {
	claims, ok := c.Get("claims")
	sub, err := claims.(jwt.MapClaims).GetSubject()
	if !ok || err != nil {
		c.JSON(401, gin.H{"error": "Unauthorized"})
		c.Abort()
		return
	}
	db := server.GetDB()
	var notes []dto.NoteDetail
	query_all_notes := `select note_id, symbol, title, content, created_at, updated_at from note where user_id = $1`
	notes = []dto.NoteDetail{}
	err2 := db.Select(&notes, query_all_notes, sub)
	if err2 != nil {
		c.JSON(500, gin.H{"error": "Internal Server Error"})
		log.Printf("Error getting notes: %v", err2)
		c.Abort()
		return
	}
	c.JSON(200, gin.H{"data": notes})
}
func GetNoteBySymbol(c *gin.Context) {
	claims, ok := c.Get("claims")
	sub, err := claims.(jwt.MapClaims).GetSubject()
	if !ok || err != nil {
		c.JSON(401, gin.H{"error": "Unauthorized"})
		c.Abort()
		return
	}
	symbol := c.Param("symbol")
	db := server.GetDB()
	var notes []dto.NoteDetail
	query_all_notes := `select note_id, symbol, title, content, created_at, updated_at from note where user_id = $1 and symbol like $2`
	notes = []dto.NoteDetail{}
	err2 := db.Select(&notes, query_all_notes, sub, symbol+"%")
	if err2 != nil {
		c.JSON(500, gin.H{"error": "Internal Server Error"})
		log.Printf("Error getting notes: %v", err2)
		c.Abort()
		return
	}
	c.JSON(200, gin.H{"data": notes})
}
func UpdateNote(c *gin.Context) {
	claims, ok := c.Get("claims")
	sub, err := claims.(jwt.MapClaims).GetSubject()
	if !ok || err != nil {
		c.JSON(401, gin.H{"error": "Unauthorized"})
		c.Abort()
		return
	}
	var data_update dto.NoteUpdate
	if errA := c.ShouldBind(&data_update); errA != nil {
		c.JSON(400, gin.H{"error": errA.Error()})
		c.Abort()
		return
	}
	db := server.GetDB()
	query_update_note := `update note set title = coalesce($1,title) , content = coalesce($2, content) where (note_id = $3 and user_id = $4)`

	tx := db.MustBegin()
	tx.MustExec(query_update_note, data_update.Title, data_update.Content, data_update.ID, sub)
	err3 := tx.Commit()
	if err3 != nil {
		c.JSON(500, gin.H{"error": "Internal Server Error"})
		log.Printf("Error updating note: %v", err3)
		c.Abort()
		return
	}
	c.JSON(200, gin.H{"data": data_update})
}
func DeleteNote(c *gin.Context) {
	claims, ok := c.Get("claims")
	sub, err := claims.(jwt.MapClaims).GetSubject()
	if !ok || err != nil {
		c.JSON(401, gin.H{"error": "Unauthorized"})
		c.Abort()
		return
	}
	note_id := c.Param("note_id")
	db := server.GetDB()
	query_delete_note := `delete from note where note_id = $1 and user_id = $2`
	tx := db.MustBegin()
	tx.MustExec(query_delete_note, note_id, sub)
	err3 := tx.Commit()
	if err3 != nil {
		c.JSON(400, gin.H{"error": "Bad Request"})
		log.Printf("Error deleting note: %v", err3)
		c.Abort()
		return
	}
	c.JSON(200, gin.H{"data": true})

}
