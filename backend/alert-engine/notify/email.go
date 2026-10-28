package notify

import (
	"alert-engine/model"
	"context"
	"encoding/json"
	"time"

	"github.com/segmentio/kafka-go"
)

// Email hands alert emails to mail-service by publishing to email_requests.
// mail-service owns SMTP and the alert_triggered template.
type Email struct {
	writer *kafka.Writer
}

func NewEmail(writer *kafka.Writer) *Email {
	return &Email{writer: writer}
}

func (e *Email) Enabled() bool { return e.writer != nil }

// emailRequest mirrors mail-service's model.EmailRequest.
type emailRequest struct {
	ID        string         `json:"id"`
	Template  string         `json:"template"`
	To        string         `json:"to"`
	Data      map[string]any `json:"data"`
	CreatedAt time.Time      `json:"created_at"`
}

// Send queues one alert email. It returns once Kafka acked the request, so a
// failure here is retried by the notifier like a failed Telegram send.
func (e *Email) Send(ctx context.Context, to string, event model.AlertTriggered) error {
	req := emailRequest{
		ID:       event.HistoryID, // lets mail-service logs be matched to alert_history
		Template: "alert_triggered",
		To:       to,
		Data: map[string]any{
			"symbol":       event.Symbol,
			"price":        event.Price,
			"conditions":   formatConditions(event),
			"triggered_at": event.TriggeredAt.Format("2006-01-02 15:04:05 MST"),
		},
		CreatedAt: time.Now().UTC(),
	}
	payload, err := json.Marshal(req)
	if err != nil {
		return err
	}
	return e.writer.WriteMessages(ctx, kafka.Message{Key: []byte(to), Value: payload})
}
