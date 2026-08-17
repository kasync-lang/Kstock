package ksocket

import (
	"context"
	"net/http/httptest"
	"testing"
)

func TestEventBusDropsWhenFull(t *testing.T) {
	bus := NewEventBus(1)
	first := Event{Key: "AAPL"}
	bus.Publish(first)
	bus.Publish(Event{Key: "MSFT"})
	if got := <-bus.subscribe(); got.Key != first.Key {
		t.Fatalf("received %#v, want key %q", got, first.Key)
	}
}

func TestSubscriptionHandlersAndPublishFiltering(t *testing.T) {
	manager := NewManager(context.Background(), NewEventBus(1))
	client := &Client{manager: manager, send: make(chan Event, 1), subs: make(map[string]bool)}
	if err := manager.eventHandler(Subscription{Type: EventSubscribe, Symbol: "AAPL"}, client); err != nil {
		t.Fatal(err)
	}
	if !client.subs["AAPL"] {
		t.Fatal("subscribe did not enable symbol")
	}
	manager.addClient(client)
	if err := manager.publish("AAPL", Event{Key: "AAPL"}); err != nil {
		t.Fatal(err)
	}
	if got := <-client.send; got.Key != "AAPL" {
		t.Fatalf("published event = %#v", got)
	}
	if err := manager.eventHandler(Subscription{Type: EventUnsubscribe, Symbol: "AAPL"}, client); err != nil {
		t.Fatal(err)
	}
	if client.subs["AAPL"] {
		t.Fatal("unsubscribe did not disable symbol")
	}
	if err := manager.publish("AAPL", Event{Key: "AAPL"}); err != nil {
		t.Fatal(err)
	}
	select {
	case got := <-client.send:
		t.Fatalf("unexpected event after unsubscribe: %#v", got)
	default:
	}
}

func TestCheckOrigin(t *testing.T) {
	for _, tc := range []struct {
		origin string
		want   bool
	}{
		{"", true}, {"localhost", true}, {"https://kasyntech.com", true}, {"https://evil.example", false},
	} {
		req := httptest.NewRequest("GET", "http://example.test/ws", nil)
		req.Header.Set("Origin", tc.origin)
		if got := checkOrigin(req); got != tc.want {
			t.Errorf("origin %q = %v, want %v", tc.origin, got, tc.want)
		}
	}
}
