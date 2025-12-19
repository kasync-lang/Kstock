package main

import (
	// "Kstock/internal/server"
	// "Kstock/pkg/jwk"
	// "fmt"

	"Kstock/internal/api"
	"Kstock/internal/server"

	"github.com/gin-gonic/gin"
)

func main() {
	server.StartServer()
	// fmt.Print(key)
	r := gin.Default()
	api.RegisterAllRoutes(r)
	r.Run(":8080")
}
