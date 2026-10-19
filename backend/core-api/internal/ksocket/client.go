package ksocket

import (
	"encoding/json"
	"log"
	"time"

	"github.com/gorilla/websocket"
)

type Client struct {
	connection *websocket.Conn
	manager    *Manager
	send       chan Event
	subs       map[string]bool
}

type ClientList map[*Client]bool

var (
	pongWait   = 10 * time.Second
	pingPeriod = (pongWait * 9) / 10
)

func NewClient(conn *websocket.Conn, manager *Manager) *Client {
	return &Client{
		connection: conn,
		manager:    manager,
		send:       make(chan Event, 256),
		subs:       make(map[string]bool),
	}
}
func (c *Client) ReadMessages() {
	defer func() {
		c.manager.removeClient(c)
	}()
	c.connection.SetReadLimit(512)
	if err := c.connection.SetReadDeadline(time.Now().Add(pongWait)); err != nil {
		log.Println("Error setting read deadline:", err)
		return
	}
	c.connection.SetPongHandler(func(string) error {
		return c.connection.SetReadDeadline(time.Now().Add(pongWait))
	})
	for {
		_, payload, err := c.connection.ReadMessage()
		if err != nil {
			if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
				log.Printf("Error reading message: %v", err)
			}
			break
		}
		var request Subscription
		if err := json.Unmarshal(payload, &request); err != nil {
			log.Println("Error unmarshaling message:", err)
			continue
		}
		log.Println(request)
		err = c.manager.eventHandler(request, c)
		if err != nil {
			log.Println("Error handling subscription:", err)
			break
		}

	}
}
func (c *Client) WriteMessages() {
	ticker := time.NewTicker(pingPeriod)
	defer func() {
		ticker.Stop()
		c.manager.removeClient(c)
	}()
	for {
		select {
		case message, ok := <-c.send:
			if !ok {
				if err := c.connection.WriteMessage(websocket.CloseMessage, nil); err != nil {
					log.Println("Connection closed:", err)
				}
				return
			}
			var tick Tick
			err := json.Unmarshal(message.Data, &tick)

			if err != nil {
				log.Println("Error marshaling1 message:", err)
				continue
			}
			if err := c.connection.WriteJSON(tick); err != nil {
				log.Println("Error writing message:", err)

			}
		case <-ticker.C:
			if err := c.connection.WriteMessage(websocket.PingMessage, []byte{}); err != nil {
				log.Println("Error writing ping message:", err)
				return
			}
		}

	}
}
