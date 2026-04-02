package main

import (
	// "Kstock/internal/server"
	// "Kstock/pkg/jwk"
	// "fmt"

	"Kstock/internal/api"
	"Kstock/internal/config"
	"Kstock/internal/server"
	"context"
	"log"
	"os"
	"os/signal"
	"syscall"

	"github.com/gin-gonic/gin"
)

func main() {
	server.StartServer()
	// fmt.Print(key)
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	var cfgKafka = server.NewKafkaListenerConfigFromConfig(config.Cfg)

	err := server.EventKafkaListener(ctx, cfgKafka, nil)
	if err != nil {
		log.Fatal(err)
	}
	r := gin.Default()
	api.RegisterAllRoutes(r)
	r.Run(":8080")

}
