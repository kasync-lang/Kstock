package model

import "time"

// EmailRequest is one message on the email_requests topic. The Kafka key is the
// recipient address.
type EmailRequest struct {
	ID        string         `json:"id"`
	Template  string         `json:"template"`
	To        string         `json:"to"`
	Data      map[string]any `json:"data"`
	CreatedAt time.Time      `json:"created_at"`
}
