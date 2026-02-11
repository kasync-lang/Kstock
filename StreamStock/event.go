package main

type Event struct {
	Key  string `json:"type"`
	Data []byte `json:"data"`
}
type Subscription struct {
	Type   string `json:"type"`
	Symbol string `json:"symbol"`
}
type EventBus struct {
	channel chan Event
}

func NewEventBus(bufferSize int) *EventBus {
	return &EventBus{
		channel: make(chan Event, bufferSize),
	}
}
func (b *EventBus) Publish(event Event) {
	select {
	case b.channel <- event:
		
	default:
	}
}
func (b *EventBus) subscribe() <-chan Event {
	return b.channel
}

type EventHandler func(event Subscription, c *Client) error

const (
	EventSubscribe   = "subscribe"
	EventUnsubscribe = "unsubscribe"
)

func handleSubscribe(event Subscription, c *Client) error {
	var symbol = event.Symbol
	c.subs[symbol] = true
	return nil
}
