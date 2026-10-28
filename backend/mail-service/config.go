package main

import (
	"os"
	"strings"
)

type Config struct {
	KafkaBrokers []string
	EmailTopic   string
	GroupID      string
	SMTPHost     string
	SMTPPort     string
	SMTPUser     string
	SMTPPassword string
	MailFrom     string
	MailFromName string
	SupportEmail string
	LogoURL      string
}

func GetEnv(key, fallback string) string {
	if v, ok := os.LookupEnv(key); ok && v != "" {
		return v
	}
	return fallback
}

func LoadConfig() *Config {
	user := GetEnv("SMTP_USER", "")
	from := GetEnv("MAIL_FROM", user) // Gmail only sends as the account itself (or a verified alias)
	return &Config{
		KafkaBrokers: splitAndTrim(GetEnv("KAFKA_BOOTSTRAP_SERVERS", "localhost:29092")),
		EmailTopic:   GetEnv("KAFKA_EMAIL_TOPIC", "email_requests"),
		GroupID:      GetEnv("KAFKA_GROUP_ID", "mail-service"),
		SMTPHost:     GetEnv("SMTP_HOST", "smtp.gmail.com"),
		SMTPPort:     GetEnv("SMTP_PORT", "587"),
		SMTPUser:     user,
		SMTPPassword: GetEnv("SMTP_PASSWORD", ""),
		MailFrom:     from,
		MailFromName: GetEnv("MAIL_FROM_NAME", "Kstock"),
		SupportEmail: GetEnv("MAIL_SUPPORT_EMAIL", from),
		LogoURL:      GetEnv("MAIL_LOGO_URL", ""),
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
