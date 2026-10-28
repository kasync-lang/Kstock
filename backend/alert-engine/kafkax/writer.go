package kafkax

import (
	"time"

	"github.com/segmentio/kafka-go"
)

// NewWriter returns a synchronous producer: WriteMessages returns only once the
// broker acked, which the outbox logic relies on before marking a row published.
func NewWriter(brokers []string, topic string) *kafka.Writer {
	return &kafka.Writer{
		Addr:         kafka.TCP(brokers...),
		Topic:        topic,
		Balancer:     &kafka.Hash{},
		RequiredAcks: kafka.RequireAll,
		BatchTimeout: 10 * time.Millisecond,
	}
}
