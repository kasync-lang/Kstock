// Package mailer turns email_requests messages into sent emails.
package mailer

import (
	"context"
	"encoding/json"
	"log"

	"mail-service/model"
	"mail-service/smtp"
	"mail-service/templates"

	"github.com/segmentio/kafka-go"
)

type Sender interface {
	Send(ctx context.Context, to, subject, htmlBody string) error
}

type Mailer struct {
	renderer *templates.Renderer
	sender   Sender
}

func New(renderer *templates.Renderer, sender Sender) *Mailer {
	return &Mailer{renderer: renderer, sender: sender}
}

// Handle is the kafkax.MessageHandler for email_requests.
//
// Returning an error makes the listener retry with backoff, so only temporary
// failures (network, SMTP 4xx such as Gmail rate limits) are returned. A request
// that can never succeed (bad JSON, unknown template, bad address, SMTP 5xx) is
// logged and dropped so it does not block the partition.
func (m *Mailer) Handle(ctx context.Context, msg kafka.Message) error {
	var req model.EmailRequest
	if err := json.Unmarshal(msg.Value, &req); err != nil {
		log.Printf("mailer: drop malformed request offset=%d err=%v", msg.Offset, err)
		return nil
	}
	if req.To == "" {
		req.To = string(msg.Key)
	}

	subject, body, err := m.renderer.Render(req.Template, req.Data)
	if err != nil {
		// Unknown template or bad data: the same request will fail the same way.
		log.Printf("mailer: drop id=%s template=%s to=%q render failed: %v", req.ID, req.Template, req.To, err)
		return nil
	}

	if err := m.sender.Send(ctx, req.To, subject, body); err != nil {
		if smtp.IsPermanent(err) {
			log.Printf("mailer: drop id=%s template=%s to=%q permanent failure: %v", req.ID, req.Template, req.To, err)
			return nil
		}
		return err
	}
	log.Printf("mailer: sent id=%s template=%s to=%q", req.ID, req.Template, req.To)
	return nil
}
