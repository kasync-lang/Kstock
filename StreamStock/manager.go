package main

import (
	"context"
	"log"
	"net/http"
	"sync"

	"github.com/gorilla/websocket"
)

var (
	websocketUpgrader = websocket.Upgrader{
		ReadBufferSize:  1024,
		WriteBufferSize: 1024,
		//CheckOrigin:     checkOrigin,
	}
	dataflow_chanel = make(chan []byte, 1000)
)

type Message struct {
	Type string `json:"type"`
	Data string `json:"data"`
}

type Manager struct {
	clients  ClientList
	handlers map[string]EventHandler
	sync.RWMutex
}

// go
func NewManager(ctx context.Context) *Manager {
	m := &Manager{
		clients:  make(map[*Client]bool),
		handlers: make(map[string]EventHandler),
	}
	m.SetupEventHandlers()
	eventBus := NewEventBus(1000)

	go GetData(ctx, eventBus)

	go func() {
		eventCh := eventBus.subscribe()
		for e := range eventCh { // sẽ kết thúc khi channel được close trong GetData
			err := m.publish(e.Key, e)
			if err != nil {
				log.Println("Error publishing event:", err)
			}
		}
		log.Println("event loop stopped")
	}()

	return m
}

func (m *Manager) SetupEventHandlers() {
	m.handlers[EventSubscribe] = handleSubscribe
}
func checkOrigin(r *http.Request) bool {
	origin := r.Header.Get("Origin")
	switch origin {
	case "http://localhost:3000", "http://":
		return true
	default:
		return false
	}
}

func (m *Manager) UpdateWebSocket(w http.ResponseWriter, r *http.Request) {
	conn, err := websocketUpgrader.Upgrade(w, r, nil)
	if err != nil {
		http.Error(w, "Could not open websocket connection", http.StatusBadRequest)
	}
	defer conn.Close()

	for {
		// Read message from browser
		var msg *Message
		err := conn.ReadJSON(msg)
		if err != nil {

			log.Println("Error read JSON")
			return
		}

		if err := conn.WriteJSON(msg); err != nil {
			log.Println("Error writing message:", err)
			return
		}

	}
}
func (m *Manager) removeClient(c *Client) {
	m.Lock()
	defer m.Unlock()
	if _, ok := m.clients[c]; ok {
		c.connection.Close()
		delete(m.clients, c)
	}
}
func (m *Manager) eventHandler(subscription Subscription, c *Client) error {
	if handler, ok := m.handlers[subscription.Type]; ok {
		return handler(subscription, c)
	}

	return nil
}
func (m *Manager) publish(symbol string, event Event) error {
	m.RLock()
	clients := make([]*Client, 0, len(m.clients))
	for client := range m.clients {
		log.Println("client:", client)
		if client.subs[symbol] {
			clients = append(clients, client)
		}
	}
	m.RUnlock()

	for _, client := range clients {
		e := event // copy
		select {
		case client.send <- e:
			log.Println("hub published event:", e.Key)
		default:
			m.removeClient(client)
		}
	}
	log.Println("hub publish finished")
	return nil
}

func (m *Manager) addClient(c *Client) {
	m.Lock()
	defer m.Unlock()
	m.clients[c] = true
}
func (m *Manager) serveWS(w http.ResponseWriter, r *http.Request) {
	log.Println("Serving WebSocket connection")
	conn, err := websocketUpgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Println("WebSocket upgrade error:", err)
		return
	}
	client := NewClient(conn, m)
	m.addClient(client)
	go client.ReadMessages()
	go client.WriteMessages()
}
