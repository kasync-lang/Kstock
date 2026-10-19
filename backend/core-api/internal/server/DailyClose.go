package server

import (
	"Kstock/internal/dto"
	"context"
	"fmt"
	"log"
	"time"

	"github.com/ClickHouse/clickhouse-go/v2"
)

const (
	// Only look at recent partitions; 30 days comfortably covers weekends/holidays.
	dailyCloseLookbackDays = 30
	// Refresh interval for the daily close cache (one light query for all symbols).
	DailyCloseRefreshInterval = time.Minute
	dailyCloseQueryTimeout    = 30 * time.Second
)

var dailyCloseStore = dto.NewDailyCloseStore()

// GetDailyCloseStore returns the process-wide cache of latest/previous daily closes.
func GetDailyCloseStore() *dto.DailyCloseStore {
	return dailyCloseStore
}

// LoadDailyCloses fetches the 2 latest daily closes of every symbol in ONE query
// and replaces the content of store.
func LoadDailyCloses(ctx context.Context, conn clickhouse.Conn, store *dto.DailyCloseStore) error {
	if conn == nil || store == nil {
		return fmt.Errorf("clickhouse conn or daily close store is nil")
	}
	ctx, cancel := context.WithTimeout(ctx, dailyCloseQueryTimeout)
	defer cancel()

	query := fmt.Sprintf(`
SELECT symbol, close
FROM ohlcv_1d
WHERE timestamp >= now() - INTERVAL %d DAY
ORDER BY symbol ASC, timestamp DESC
LIMIT 2 BY symbol`, dailyCloseLookbackDays)

	rows, err := conn.Query(ctx, query)
	if err != nil {
		return err
	}
	defer func() { _ = rows.Close() }()

	data := make(map[string]dto.DailyClose)
	for rows.Next() {
		var (
			symbol string
			price  float64
		)
		if err := rows.Scan(&symbol, &price); err != nil {
			return err
		}
		// Rows come ordered by timestamp DESC within each symbol:
		// first row = latest close, second row = previous close.
		dc := data[symbol]
		if !dc.HasLast {
			dc.Last, dc.HasLast = price, true
		} else if !dc.HasPrev {
			dc.Prev, dc.HasPrev = price, true
		}
		data[symbol] = dc
	}
	if err := rows.Err(); err != nil {
		return err
	}
	store.ReplaceAll(data)
	return nil
}

// RunDailyCloseRefresher reloads the cache every interval until ctx is cancelled.
// On error the previous cache content is kept.
func RunDailyCloseRefresher(ctx context.Context, conn clickhouse.Conn, store *dto.DailyCloseStore, interval time.Duration) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			if err := LoadDailyCloses(ctx, conn, store); err != nil {
				log.Printf("refresh daily close cache: %v", err)
			}
		}
	}
}

