package server

import (
	"Kstock/internal/config"
	"Kstock/pkg/jwt"
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
	_, err2 := IntiDB()
	if err2 != nil {
		log.Printf("Init DB error, %s", err.Error())
	} else {
		log.Printf("Init DB success")
	}
	if _, err := jwt.GetKeystore(); err != nil {
		log.Fatal("JWT Keystore Error")
	} else {
		log.Printf("JWT Keystore success")
	}
}
