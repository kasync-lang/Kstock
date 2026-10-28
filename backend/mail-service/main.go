// mail-service renders and sends every Kstock email. Other services publish a
// {template, to, data} request and never touch SMTP credentials themselves.
//
//	auth-service, alert-engine ──▶ email_requests ──▶ mailer (render template) ──▶ SMTP (Gmail)
package main

import (
	"context"
	"errors"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"mail-service/kafkax"
	"mail-service/mailer"
	"mail-service/smtp"
	"mail-service/templates"

	"github.com/joho/godotenv"
	"github.com/segmentio/kafka-go"
)

func main() {
	if err := godotenv.Load(".env"); err != nil {
		log.Printf("no .env file, using environment: %v", err)
	}
	cfg := LoadConfig()

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	if cfg.MailFrom == "" {
		// Don't crash-loop on a fresh checkout: requests wait in Kafka and are
		// sent once MAIL_FROM/SMTP_* are set and the service restarts.
		log.Printf("mail-service disabled: set SMTP_USER (or MAIL_FROM) and SMTP_PASSWORD; requests stay queued in %s", cfg.EmailTopic)
		<-ctx.Done()
		return
	}

	renderer, err := templates.New(map[string]any{
		"app_name":      cfg.MailFromName,
		"project_name":  cfg.MailFromName,
		"support_email": cfg.SupportEmail,
		"logo_url":      cfg.LogoURL,
		"year":          time.Now().Year(),
	})
	if err != nil {
		log.Fatalf("load templates: %v", err)
	}

	sender, err := smtp.NewSender(smtp.Config{
		Host:     cfg.SMTPHost,
		Port:     cfg.SMTPPort,
		User:     cfg.SMTPUser,
		Password: cfg.SMTPPassword,
		From:     cfg.MailFrom,
		FromName: cfg.MailFromName,
	})
	if err != nil {
		log.Fatalf("smtp config: %v", err)
	}

	log.Printf("mail-service started: smtp=%s:%s from=%s templates=%v", cfg.SMTPHost, cfg.SMTPPort, cfg.MailFrom, templates.Names())
	err = kafkax.Listen(ctx, kafkax.ListenerConfig{
		Brokers:      cfg.KafkaBrokers,
		Topic:        cfg.EmailTopic,
		GroupID:      cfg.GroupID,
		MaxRetries:   5,
		RetryBackoff: 2 * time.Second,
	}, exitOnAuthError(mailer.New(renderer, sender).Handle))
	if err != nil {
		log.Fatalf("listener: %v", err)
	}
	log.Printf("mail-service stopped")
}

// exitOnAuthError stops the process when Gmail rejects the credentials. The
// message stays uncommitted, so nothing is lost: it is sent after SMTP_* is
// fixed and the container restarts, instead of every queued email being
// retried and skipped one after another.
func exitOnAuthError(handle kafkax.MessageHandler) kafkax.MessageHandler {
	return func(ctx context.Context, msg kafka.Message) error {
		err := handle(ctx, msg)
		if errors.Is(err, smtp.ErrAuth) {
			log.Fatalf("mail-service: %v; check SMTP_USER/SMTP_PASSWORD (Gmail needs an app password)", err)
		}
		return err
	}
}
