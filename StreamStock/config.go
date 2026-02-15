package main

import (
	"log"
	"os"
	"strconv"

	"github.com/joho/godotenv"
)

type Config struct {
	Env          string
	KAFKAHost    string
	KAFKAPort    int
	KAFKAGroupID string
	KAFKATopic   string
}

func Load() Config {
	env := GetEnv("APP_ENV", "development")
	if env == "development" {
		_ = godotenv.Load()
	}
	kafkaPort, err := strconv.Atoi(MustGetEnv("KAFKA_PORT"))
	if err != nil {
		log.Fatalf("Invalid KAFKA_PORT: %v", err)
	}
	return Config{
		Env:          env,
		KAFKAHost:    MustGetEnv("KAFKA_HOST"),
		KAFKAPort:    kafkaPort,
		KAFKAGroupID: GetEnv("KAFKA_GROUP_ID", ""),
		KAFKATopic:   MustGetEnv("KAFKA_TOPIC"),
	}

}
func GetEnv(key, fallback string) string {
	val := os.Getenv(key)
	if val == "" {
		return fallback
	}
	return val
}
func MustGetEnv(key string) string {
	val := os.Getenv(key)
	if val == "" {
		log.Fatalf("Environment variable %s is required but not set", key)
	}
	return val
}
