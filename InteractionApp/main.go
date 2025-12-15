package main

import (
	// "Kstock/internal/server"
	// "Kstock/pkg/jwt"
	// "fmt"

	"Kstock/internal/api"
	"Kstock/internal/server"
	"Kstock/pkg/jwt"

	"github.com/gin-gonic/gin"
)

func main() {
	server.StartServer()
	key, err := jwt.GetRawJWK()
	// fmt.Print(key)
	r := gin.Default()

	api.RegisterAllRoutes(r)
	r.Run(":8080")
}
