package server

import (
	"Kstock/internal/config"
	"context"
	"errors"
	"log"
	"strings"
	"time"

	"github.com/segmentio/kafka-go"
)

type KafkaMessageHandler func(ctx context.Context, msg kafka.Message) error

type KafkaListenerConfig struct {
	Brokers      []string
	Topic        string
	GroupID      string
	MinBytes     int
	MaxBytes     int
	MaxWait      time.Duration
	MaxRetries   int
	RetryBackoff time.Duration
}

func (c *KafkaListenerConfig) applyDefault() {
	if c.MinBytes <= 0 {
		c.MinBytes = 10e2
	}
	if c.MaxBytes <= 0 {
		c.MaxBytes = 10e6
	}
	if c.MaxWait <= 0 {
		c.MaxWait = 5 * time.Second
	}
	if c.MaxRetries < 0 {
		c.MaxRetries = 5
	}
	if c.RetryBackoff <= 0 {
		c.RetryBackoff = 500 * time.Millisecond
	}
}

func NewKafkaListenerConfigFromConfig(cfg *config.Config) KafkaListenerConfig {
	brokers := splitAndTrim(cfg.KafkaBootrapServer)

	listenerCfg := KafkaListenerConfig{
		Brokers: brokers,
		Topic:   cfg.KafkaTopic,
		GroupID: cfg.KafkaGroupID,
	}
	listenerCfg.applyDefault()

	return listenerCfg
}

func EventKafkaListener(ctx context.Context, cfg KafkaListenerConfig, handler KafkaMessageHandler) error {
	if err := validateListenerConfig(cfg); err != nil {
		return err
	}
	if handler == nil {
		return errors.New("kafka listener: handler is nil")
	}

	cfg.applyDefault()
	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:  cfg.Brokers,
		Topic:    cfg.Topic,
		GroupID:  cfg.GroupID,
		MinBytes: cfg.MinBytes,
		MaxBytes: cfg.MaxBytes,
		MaxWait:  cfg.MaxWait,
	})
	reader.SetOffset(kafka.LastOffset)
	defer func() {
		if err := reader.Close(); err != nil {
			log.Printf("kafka listener: close reader error topic=%s group=%s err=%v", cfg.Topic, cfg.GroupID, err)
		}
	}()

	log.Printf("kafka listener: started topic=%s group=%s brokers=%v", cfg.Topic, cfg.GroupID, cfg.Brokers)

	for {
		msg, err := reader.FetchMessage(ctx)
		if err != nil {
			if errors.Is(err, context.Canceled) || errors.Is(err, context.DeadlineExceeded) || ctx.Err() != nil {
				log.Printf("kafka listener: shutdown topic=%s group=%s", cfg.Topic, cfg.GroupID)
				return nil
			}

			log.Printf("kafka listener: fetch error topic=%s group=%s err=%v", cfg.Topic, cfg.GroupID, err)
			continue
		}

		err = processWithRetry(ctx, cfg, msg, handler)
		if err != nil {
			// Keep offset uncommitted so message can be reprocessed by the group.
			log.Printf("kafka listener: handle failed topic=%s partition=%d offset=%d key=%s err=%v", cfg.Topic, msg.Partition, msg.Offset, string(msg.Key), err)
			continue
		}

		if err := reader.CommitMessages(ctx, msg); err != nil {
			log.Printf("kafka listener: commit failed topic=%s partition=%d offset=%d err=%v", cfg.Topic, msg.Partition, msg.Offset, err)
			continue
		}
	}
}

func processWithRetry(ctx context.Context, cfg KafkaListenerConfig, msg kafka.Message, handler KafkaMessageHandler) error {
	var lastErr error

	for attempt := 0; attempt <= cfg.MaxRetries; attempt++ {
		if err := ctx.Err(); err != nil {
			return err
		}

		if err := handler(ctx, msg); err == nil {
			return nil
		} else {
			lastErr = err
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

func validateListenerConfig(cfg KafkaListenerConfig) error {
	if len(cfg.Brokers) == 0 {
		return errors.New("kafka listener: brokers is required")
	}
	if cfg.Topic == "" {
		return errors.New("kafka listener: topic is required")
	}
	if cfg.GroupID == "" {
		return errors.New("kafka listener: groupID is required")
	}

	return nil
}

func splitAndTrim(raw string) []string {
	if raw == "" {
		return nil
	}

	parts := strings.Split(raw, ",")
	result := make([]string, 0, len(parts))
	for _, p := range parts {
		v := strings.TrimSpace(p)
		if v != "" {
			result = append(result, v)
		}
	}

	return result
}
