package handle

import (
	"Kstock/internal/server"
	"log"

	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
)

func GetAllFavorite(c *gin.Context) {
	claims, ok := c.Get("claims")
	sub, err := claims.(jwt.MapClaims).GetSubject()
	if !ok || err != nil {
		c.JSON(401, gin.H{"error": "Unauthorized"})
		c.Abort()
		return
	}
	query_get_favorite := `select symbol from favorite_symbols where user_id = $1`
	db := server.GetDB()
	rows, err := db.Queryx(query_get_favorite, sub)
	if err != nil {
		log.Println(err)
		c.JSON(500, gin.H{"error": "Internal Server Error"})
		c.Abort()
		return
	}
	symbols := []string{}
	for rows.Next() {
		var symbol string
		if err := rows.Scan(&symbol); err != nil {
			log.Println(err)
			c.JSON(500, gin.H{"error": "Internal Server Error"})
			c.Abort()
			return
		}
		symbols = append(symbols, symbol)

	}
	if err := rows.Err(); err != nil {
		log.Println(err)
		c.JSON(500, gin.H{"error": "Internal Server Error"})
		c.Abort()
		return
	}
	c.JSON(200, gin.H{"data": symbols})
}

func AddFavorite(c *gin.Context) {
	claims, ok := c.Get("claims")
	sub, err := claims.(jwt.MapClaims).GetSubject()
	if !ok || err != nil {
		c.JSON(401, gin.H{"error": "Unauthorized"})
		c.Abort()
		return
	}
	db := server.GetDB()
	symbol := c.Param("symbol")
	query_add_favorite := `insert into favorite_symbols (user_id, symbol) values ($1, $2) on conflict (user_id, symbol) do nothing`
	_, err = db.Exec(query_add_favorite, sub, symbol)
	if err != nil {
		log.Println(err)
		c.JSON(500, gin.H{"error": "Internal Server Error"})
		c.Abort()
		return
	}
	c.JSON(200, gin.H{"message": "Favorite added successfully"})
}
func RemoveFavorite(c *gin.Context) {
	claims, ok := c.Get("claims")
	sub, err := claims.(jwt.MapClaims).GetSubject()
	if !ok || err != nil {
		c.JSON(401, gin.H{"error": "Unauthorized"})
		c.Abort()
		return
	}
	db := server.GetDB()
	symbol := c.Param("symbol")
	query_remove_favorite := `delete from favorite_symbols where user_id = $1 and symbol = $2 `
	_, err = db.Exec(query_remove_favorite, sub, symbol)
	if err != nil {
		log.Println(err)
		c.JSON(500, gin.H{"error": "Internal Server Error"})
		c.Abort()
		return
	}
	c.JSON(200, gin.H{"message": "Favorite removed successfully"})
}
