package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"time"

	"github.com/segmentio/kafka-go"
)

// go
func GetData(ctx context.Context, bus *EventBus, cfg *Config) {
	broker := []string{fmt.Sprintf("%s:%d", cfg.KAFKAHost, cfg.KAFKAPort)}

	r := kafka.NewReader(kafka.ReaderConfig{
		Brokers:     broker,
		Topic:       cfg.KAFKATopic,
		GroupID:     cfg.KAFKAGroupID,
		MinBytes:    10e3,
		MaxBytes:    10e6,
		StartOffset: kafka.LastOffset,
	})
	defer r.Close()

	log.Println("Getting Data......")

	backoff := time.Second

	for {
		m, err := r.ReadMessage(ctx)
		if err != nil {
			// 1. Context bị cancel → shutdown
			if errors.Is(err, context.Canceled) ||
				errors.Is(err, context.DeadlineExceeded) {
				log.Println("kafka reader stopped by context")
				close(bus.channel)
				return
			}

			// 2. Error tạm thời → retry
			log.Println("read error, retrying:", err)
			time.Sleep(backoff)

			// exponential backoff (có trần)
			if backoff < 30*time.Second {
				backoff *= 2
			}
			continue
		}

		// reset backoff khi đọc thành công
		backoff = time.Second
		bus.Publish(Event{
			Key:  string(m.Key),
			Data: m.Value,
		})
	}
}
