package server

import (
	"Kstock/internal/config"
	"Kstock/pkg/jwk"
	"log"

	"github.com/joho/godotenv"
)

func StartServer() {

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
}
