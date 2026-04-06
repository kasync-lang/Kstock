package server

import (
	"Kstock/internal/dto"
	"context"
	"encoding/json"

	"github.com/segmentio/kafka-go"
)

type PriceUpdater interface {
	Update(symbol string, price float64)
}

func NewPriceHandler(store PriceUpdater) KafkaMessageHandler {
	return func(ctx context.Context, msg kafka.Message) error {
		symbol := string(msg.Key)
		var valueData dto.Tick
		err := json.Unmarshal(msg.Value, &valueData)
		if err != nil {
			return err
		}
		price := valueData.P
		store.Update(symbol, price)
		return nil
	}
}
