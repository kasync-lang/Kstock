package main

import (
	"fmt"
	"os"
	"strings"
)

type Config struct {
	KafkaBrokers     []string
	TickTopic        string
	TickGroupID      string
	TriggeredTopic   string
	NotifierGroupID  string
	PostgresDSN      string
	TelegramBotToken string
	EmailTopic       string
}

func GetEnv(key, fallback string) string {
	if v, ok := os.LookupEnv(key); ok && v != "" {
		return v
	}
	return fallback
}

func LoadConfig() *Config {
	dsn := fmt.Sprintf("host=%s port=%s user=%s password=%s dbname=%s sslmode=disable connect_timeout=5",
		GetEnv("POSTGRES_HOST", "localhost"),
		GetEnv("POSTGRES_PORT", "5432"),
		GetEnv("POSTGRES_USER", "postgres"),
		GetEnv("POSTGRES_PASSWORD", "postgres"),
		GetEnv("POSTGRES_DB", "interactdb"),
	)
	return &Config{
		KafkaBrokers:     splitAndTrim(GetEnv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")),
		TickTopic:        GetEnv("KAFKA_TICK_TOPIC", "raw_data_trade"),
		TickGroupID:      GetEnv("KAFKA_GROUP_ID", "alert-engine"),
		TriggeredTopic:   GetEnv("KAFKA_TRIGGERED_TOPIC", "alert_triggered"),
		NotifierGroupID:  GetEnv("KAFKA_NOTIFIER_GROUP_ID", "alert-notifier"),
		PostgresDSN:      dsn,
		TelegramBotToken: GetEnv("TELEGRAM_BOT_TOKEN", ""),
		EmailTopic:       GetEnv("KAFKA_EMAIL_TOPIC", "email_requests"),
	}
}

func splitAndTrim(raw string) []string {
	parts := strings.Split(raw, ",")
	result := make([]string, 0, len(parts))
	for _, p := range parts {
		if v := strings.TrimSpace(p); v != "" {
			result = append(result, v)
		}
	}
	return result
}
