package test

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"Kstock/internal/ksocket"

	"github.com/gorilla/websocket"
)

func TestServeWSAndPublish(t *testing.T) {
	bus := ksocket.NewEventBus(4)
	manager := ksocket.NewManager(context.Background(), bus)

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		manager.ServeWS(w, r)
	}))
	defer srv.Close()

	wsURL := "ws" + strings.TrimPrefix(srv.URL, "http")
	conn, _, err := websocket.DefaultDialer.Dial(wsURL, http.Header{})
	if err != nil {
		t.Fatalf("websocket dial error: %v", err)
	}
	defer conn.Close()

	sub := ksocket.Subscription{Type: ksocket.EventSubscribe, Symbol: "AAPL"}
	payload, err := json.Marshal(sub)
	if err != nil {
		t.Fatalf("marshal subscribe error: %v", err)
	}
	if err := conn.WriteMessage(websocket.TextMessage, payload); err != nil {
		t.Fatalf("write subscribe error: %v", err)
	}

	time.Sleep(50 * time.Millisecond)

	expected := ksocket.Tick{P: 101.5, S: "AAPL", T: 123, V: 10}
	data, err := json.Marshal(expected)
	if err != nil {
		t.Fatalf("marshal tick error: %v", err)
	}
	bus.Publish(ksocket.Event{Key: "AAPL", Data: data})

	_ = conn.SetReadDeadline(time.Now().Add(2 * time.Second))
	var got ksocket.Tick
	if err := conn.ReadJSON(&got); err != nil {
		t.Fatalf("read tick error: %v", err)
	}
	if got.S != expected.S || got.P != expected.P || got.V != expected.V {
		t.Fatalf("unexpected tick: %#v", got)
	}
}


