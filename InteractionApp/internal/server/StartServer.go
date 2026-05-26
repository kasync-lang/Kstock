package server

import (
	"Kstock/internal/config"
	"Kstock/internal/ksocket"
	"Kstock/pkg/jwk"
	"context"
	"errors"
	"log"

	"github.com/joho/godotenv"
)

var (
	eventBus *ksocket.EventBus
	manager  *ksocket.Manager
)

func StartServer(ctx context.Context) {

	err := godotenv.Load(".env")
	if err != nil {
		log.Printf("Error loading .env file: %v", err.Error())
	}

	cfg := config.LoadConfig()
	if cfg == nil {
		log.Printf("Load Config error")
	} else {
		log.Printf("Load Config success")
	}
	log.Printf("Starting Server")

	if _, err := jwk.GetKeystore(); err != nil {
		log.Fatal("JWT Keystore Error", err.Error())
	} else {
		log.Printf("JWT Keystore success")
	}
	instance, err2 := IntiDB()
	if err2 != nil {
		log.Fatal("Init DB error", err2)
	} else {
		log.Printf("Init DB success %v", instance)
	}
	chConn, chErr := InitClickHouse()
	if chErr != nil {
		log.Fatal("Init ClickHouse error", chErr)
	} else {
		log.Printf("Init ClickHouse success %v", chConn != nil)
	}
	if InitSocket(ctx) != nil {
		log.Fatal("Init Socket error")
	} else {
		log.Printf("Init Socket success")
	}
}
func InitSocket(ctx context.Context) error {
	eventBus = ksocket.NewEventBus(1000)
	manager = ksocket.NewManager(ctx, eventBus)
	if eventBus == nil || manager == nil {
		return errors.New("Event Bus Error")
	}
	return nil
}
func GetEventBus() *ksocket.EventBus {
	return eventBus
}
func GetManager() *ksocket.Manager {
	return manager
}
