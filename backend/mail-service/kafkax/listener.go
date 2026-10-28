// Package kafkax holds the Kafka consumer helper. The listener is the
// same pattern as core-api's internal/server/EventKafkaListener.go (copied, not
// imported, so this service builds without core-api's source).
package kafkax

import (
	"context"
	"errors"
	"log"
	"time"

	"github.com/segmentio/kafka-go"
)

type MessageHandler func(ctx context.Context, msg kafka.Message) error

type ListenerConfig struct {
	Brokers      []string
	Topic        string
	GroupID      string
	MaxRetries   int
	RetryBackoff time.Duration
}

// Listen consumes Topic as part of GroupID until ctx is cancelled. A message is
// committed only after handler succeeds, so a crash replays it (at-least-once).
func Listen(ctx context.Context, cfg ListenerConfig, handler MessageHandler) error {
	if len(cfg.Brokers) == 0 || cfg.Topic == "" || cfg.GroupID == "" {
		return errors.New("kafka listener: brokers, topic and groupID are required")
	}
	if cfg.RetryBackoff <= 0 {
		cfg.RetryBackoff = 500 * time.Millisecond
	}

	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:     cfg.Brokers,
		Topic:       cfg.Topic,
		GroupID:     cfg.GroupID,
		MinBytes:    1,
		MaxBytes:    10e6,
		MaxWait:     500 * time.Millisecond,
		// Unlike alert-engine's tick listener, start from the oldest message when
		// the group has no committed offset yet: requests queued before the first
		// run (or while SMTP was unconfigured) must still be sent.
		StartOffset: kafka.FirstOffset,
	})
	defer func() {
		if err := reader.Close(); err != nil {
			log.Printf("kafka listener: close reader error topic=%s group=%s err=%v", cfg.Topic, cfg.GroupID, err)
		}
	}()

	log.Printf("kafka listener: started topic=%s group=%s brokers=%v", cfg.Topic, cfg.GroupID, cfg.Brokers)

	for {
		msg, err := reader.FetchMessage(ctx)
		if err != nil {
			if ctx.Err() != nil {
				log.Printf("kafka listener: shutdown topic=%s group=%s", cfg.Topic, cfg.GroupID)
				return nil
			}
			log.Printf("kafka listener: fetch error topic=%s group=%s err=%v", cfg.Topic, cfg.GroupID, err)
			continue
		}

		if err := processWithRetry(ctx, cfg, msg, handler); err != nil {
			// Keep offset uncommitted so message can be reprocessed by the group.
			log.Printf("kafka listener: handle failed topic=%s partition=%d offset=%d key=%s err=%v", cfg.Topic, msg.Partition, msg.Offset, string(msg.Key), err)
			continue
		}

		if err := reader.CommitMessages(ctx, msg); err != nil {
			log.Printf("kafka listener: commit failed topic=%s partition=%d offset=%d err=%v", cfg.Topic, msg.Partition, msg.Offset, err)
		}
	}
}

func processWithRetry(ctx context.Context, cfg ListenerConfig, msg kafka.Message, handler MessageHandler) error {
	var lastErr error
	for attempt := 0; attempt <= cfg.MaxRetries; attempt++ {
		if err := ctx.Err(); err != nil {
			return err
		}
		if lastErr = handler(ctx, msg); lastErr == nil {
			return nil
		}
		if attempt == cfg.MaxRetries {
			break
		}

		backoff := cfg.RetryBackoff * time.Duration(1<<attempt)
		log.Printf("kafka listener: retry attempt=%d topic=%s partition=%d offset=%d wait=%s err=%v", attempt+1, cfg.Topic, msg.Partition, msg.Offset, backoff, lastErr)

		timer := time.NewTimer(backoff)
		select {
		case <-ctx.Done():
			timer.Stop()
			return ctx.Err()
		case <-timer.C:
		}
	}
	return lastErr
}
