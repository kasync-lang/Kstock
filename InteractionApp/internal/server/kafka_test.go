package server

import (
	"context"
	"errors"
	"sync/atomic"
	"testing"
	"time"

	"github.com/segmentio/kafka-go"
)

type recordingPriceStore struct {
	symbol string
	price  float64
}

func (s *recordingPriceStore) Update(symbol string, price float64) { s.symbol, s.price = symbol, price }

func TestKafkaConfigHelpers(t *testing.T) {
	if got := splitAndTrim(" kafka-1:9092, ,kafka-2:9092 "); len(got) != 2 || got[0] != "kafka-1:9092" || got[1] != "kafka-2:9092" {
		t.Fatalf("splitAndTrim returned %#v", got)
	}
	for _, tc := range []struct {
		cfg  KafkaListenerConfig
		want string
	}{
		{KafkaListenerConfig{}, "brokers"},
		{KafkaListenerConfig{Brokers: []string{"broker"}}, "topic"},
		{KafkaListenerConfig{Brokers: []string{"broker"}, Topic: "ticks"}, "groupID"},
	} {
		if err := validateListenerConfig(tc.cfg); err == nil || !contains(err.Error(), tc.want) {
			t.Errorf("validateListenerConfig(%+v) error = %v, want %q", tc.cfg, err, tc.want)
		}
	}
	cfg := KafkaListenerConfig{MaxRetries: -1}
	cfg.applyDefault()
	if cfg.MinBytes != 1000 || cfg.MaxBytes != 10000000 || cfg.MaxRetries != 5 || cfg.RetryBackoff != 500*time.Millisecond {
		t.Fatalf("defaults = %+v", cfg)
	}
}

func TestProcessWithRetry(t *testing.T) {
	var calls atomic.Int32
	cfg := KafkaListenerConfig{MaxRetries: 2, RetryBackoff: time.Millisecond}
	err := processWithRetry(context.Background(), cfg, kafka.Message{}, func(context.Context, kafka.Message) error {
		if calls.Add(1) < 3 {
			return errors.New("temporary")
		}
		return nil
	})
	if err != nil || calls.Load() != 3 {
		t.Fatalf("err=%v calls=%d, want success after 3", err, calls.Load())
	}

	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if err := processWithRetry(ctx, cfg, kafka.Message{}, func(context.Context, kafka.Message) error { return nil }); !errors.Is(err, context.Canceled) {
		t.Fatalf("canceled process error = %v", err)
	}
}

func TestPriceHandlerUpdatesStore(t *testing.T) {
	if err := InitSocket(context.Background()); err != nil {
		t.Fatalf("InitSocket: %v", err)
	}
	store := &recordingPriceStore{}
	handler := NewPriceHandler(store)
	if err := handler(context.Background(), kafka.Message{Key: []byte("AAPL"), Value: []byte(`{"p":123.45,"s":"AAPL"}`)}); err != nil {
		t.Fatalf("handler error: %v", err)
	}
	if store.symbol != "AAPL" || store.price != 123.45 {
		t.Fatalf("store = %#v", store)
	}
	if err := handler(context.Background(), kafka.Message{Value: []byte("not-json")}); err == nil {
		t.Fatal("invalid JSON unexpectedly succeeded")
	}
}

func contains(s, part string) bool {
	for i := 0; i+len(part) <= len(s); i++ {
		if s[i:i+len(part)] == part {
			return true
		}
	}
	return false
}
