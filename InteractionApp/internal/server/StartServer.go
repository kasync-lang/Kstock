package server

import (
	"Kstock/internal/config"
	"Kstock/internal/dto"
	"Kstock/internal/ksocket"
	"context"
	"errors"
	"log"

	"github.com/ClickHouse/clickhouse-go/v2"
	"github.com/joho/godotenv"
)

var (
	eventBus *ksocket.EventBus
	manager  *ksocket.Manager
)

func StartServer(ctx context.Context, priceStore *dto.PriceStore) {

	err := godotenv.Load(".env")
	if err != nil {
		log.Printf("Error loading .env file: %v", err.Error())
	}

	cfg := config.LoadConfig()
	if cfg == nil {
		log.Printf("Load Config error")
	} else {
		log.Printf("Load Config success")
	}
	log.Printf("Starting Server")

	instance, err2 := IntiDB()
	if err2 != nil {
		log.Fatal("Init DB error", err2)
	} else {
		log.Printf("Init DB success %v", instance)
	}
	chConn, chErr := InitClickHouse()
	if chErr != nil {
		log.Fatal("Init ClickHouse error", chErr)
	} else {
		log.Printf("Init ClickHouse success %v", chConn != nil)
	}
	if InitSocket(ctx) != nil {
		log.Fatal("Init Socket error")
	} else {
		log.Printf("Init Socket success")
	}
	err = InitFristPriceStore(ctx, priceStore, chConn)
	if err != nil {
		log.Printf("Init PriceStore error %v %v", err, priceStore)
	} else {
		log.Printf("Init PriceStore success")
	}
}
func InitSocket(ctx context.Context) error {
	eventBus = ksocket.NewEventBus(1000)
	manager = ksocket.NewManager(ctx, eventBus)
	if eventBus == nil || manager == nil {
		return errors.New("Event Bus Error")
	}
	return nil
}
func GetEventBus() *ksocket.EventBus {
	return eventBus
}
func GetManager() *ksocket.Manager {
	return manager
}
func InitFristPriceStore(ctx context.Context, priceStore *dto.PriceStore, conn clickhouse.Conn) error {
	var firstPrice []dto.FirstPrice
	query_get_last_price := "SELECT symbol, argMax(close, timestamp) as price from ohlcv_1d group by symbol"
	rows, err := conn.Query(ctx, query_get_last_price)
	if err != nil {
		return err
	}
	defer rows.Close()
	for rows.Next() {
		var fp dto.FirstPrice
		if err := rows.Scan(&fp.Symbol, &fp.Price); err != nil {
			return err
		}
		firstPrice = append(firstPrice, fp)
		priceStore.Update(fp.Symbol, fp.Price)
	}
	priceStore.Update("USD", 1.0)
	return nil
}
