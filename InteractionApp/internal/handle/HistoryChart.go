package handle

import (
	"Kstock/internal/config"
	"Kstock/internal/dto"
	"Kstock/internal/server"
	"context"
	"errors"
	"fmt"
	"log"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
)

type historyResponse dto.HistoryResponse
type CandleResponse dto.Candle

// GetHistoryChart godoc
// @Summary Get historical chart candles
// @Description Returns OHLCV arrays for the requested symbol and time range.
// @Tags history
// @Produce json
// @Param symbol query string true "Stock ticker symbol"
// @Param from query int64 true "Unix timestamp for start time"
// @Param to query int64 false "Unix timestamp for end time (defaults to now)"
// @Param resolution query string false "Candle resolution (e.g. 1m, 5m, 1h, 1D). Defaults to 1D"
// @Success 200 {object} dto.HistoryResponse
// @Failure 400 {object} map[string]string
// @Failure 500 {object} map[string]string
// @Router /chart/history [get]
func GetHistoryChart(c *gin.Context) {
	resolution := c.DefaultQuery("resolution", "1D")
	symbol := c.Query("symbol")
	from := c.Query("from")
	to := c.DefaultQuery("to", strconv.FormatInt(time.Now().UTC().Unix(), 10))

	if symbol == "" || from == "" {
		c.JSON(http.StatusBadRequest, gin.H{"error": "missing required query params: symbol, from"})
		return
	}

	fromUnix, err := strconv.ParseInt(from, 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid from"})
		return
	}
	toUnix, err := strconv.ParseInt(to, 10, 64)
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "invalid to"})
		return
	}
	if config.Cfg == nil {
		config.LoadConfig()
	}
	if config.Cfg == nil || config.Cfg.ClickHouseDatabase == "" {
		c.AbortWithStatus(http.StatusInternalServerError)
		log.Print("clickhouse database not configured")
		return
	}

	conn := server.GetClickHouse()
	if conn == nil {
		if _, err := server.InitClickHouse(); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "clickhouse not initialized"})
			log.Println(err)
			return
		}
		conn = server.GetClickHouse()
	}
	table, err1 := resolutionToTableName(resolution)
	if err1 != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "unsupported resolution"})
		return
	}
	query := fmt.Sprintf("SELECT symbol, timestamp, open, high, low, close, volume FROM %s.%s WHERE symbol = ? AND timestamp >= ? AND timestamp <= ? ORDER BY timestamp ASC", config.Cfg.ClickHouseDatabase, table)

	rows, err := conn.Query(c.Request.Context(), query, symbol, time.Unix(fromUnix, 0).UTC(), time.Unix(toUnix, 0).UTC())
	if err != nil {
		c.AbortWithStatus(http.StatusInternalServerError)
		log.Println(err.Error())
		return
	}
	defer rows.Close()

	resp := historyResponse{S: symbol}
	for rows.Next() {
		var candle CandleResponse
		if err := rows.Scan(&candle.Symbol, &candle.Timestamp, &candle.Open, &candle.High, &candle.Low, &candle.Close, &candle.Volume); err != nil {
			c.AbortWithStatus(http.StatusInternalServerError)
			log.Println(err.Error())
			return
		}
		resp.T = append(resp.T, candle.Timestamp.Unix())
		resp.O = append(resp.O, candle.Open)
		resp.H = append(resp.H, candle.High)
		resp.L = append(resp.L, candle.Low)
		resp.C = append(resp.C, candle.Close)
		resp.V = append(resp.V, candle.Volume)
	}
	if len(resp.T) == 0 {
		c.JSON(http.StatusOK, historyResponse{S: "no_data"})
		return
	}
	c.JSON(http.StatusOK, resp)
}

func resolutionToInterval(resolution string) (string, bool) {
	switch resolution {
	case "1", "1m", "1M":
		return "1 MINUTE", true
	case "5", "5m":
		return "5 MINUTE", true
	case "15", "15m":
		return "15 MINUTE", true
	case "60", "1H", "1h":
		return "1 HOUR", true
	case "1D", "1d":
		return "1 DAY", true
	case "1W", "1w":
		return "1 WEEK", true
	}

	res := strings.TrimSpace(resolution)
	if res == "" {
		return "", false
	}
	unit := res[len(res)-1:]
	valuePart := res[:len(res)-1]
	if unit != "m" && unit != "h" && unit != "d" {
		return "", false
	}
	value, err := strconv.Atoi(valuePart)
	if err != nil || value <= 0 {
		return "", false
	}
	if unit == "m" {
		return fmt.Sprintf("%d MINUTE", value), true
	}
	if unit == "h" {
		return fmt.Sprintf("%d HOUR", value), true
	}
	return fmt.Sprintf("%d DAY", value), true
}

// resolutionToTableName returns the ClickHouse table name for a given resolution.
// Examples: "1m" -> "history_1m", "1h" -> "history_1h", "1D" -> "history_1d"
func resolutionToTableName(resolution string) (string, error) {
	res := strings.TrimSpace(strings.ToLower(resolution))
	switch res {
	case "1", "1m", "1M":
		return "ohlcv_1m", nil
	case "5", "5m":
		return "ohlcv_5m", nil
	case "15", "15m":
		return "ohlcv_15m", nil
	case "30", "30m":
		return "ohlcv_30m", nil
	case "60", "1h", "1H":
		return "ohlcv_1h", nil
	case "1d", "1D":
		return "ohlcv_1d", nil
	case "1w", "1W":
		return "ohlcv_1w", nil
	default:
		return "", errors.New("invalid resolution")
	}
}

// ensureResolutionTable creates the resolution table if it does not exist.
func ensureResolutionTable(ctx context.Context, conn interface {
	Exec(context.Context, string, ...interface{}) error
}, db, table string) error {
	// columns: s String, t DateTime, o Float64, h Float64, l Float64, c Float64, v Float64
	create := fmt.Sprintf(`CREATE TABLE IF NOT EXISTS %s.%s (
		s String,
		t DateTime,
		o Float64,
		h Float64,
		l Float64,
		c Float64,
		v Float64
	) ENGINE = MergeTree()
	ORDER BY (s, t)`, db, table)
	return conn.Exec(ctx, create)
}

// insertIntoResolutionTable inserts an aggregated candle into the resolution table.
func insertIntoResolutionTable(ctx context.Context, conn interface {
	Exec(context.Context, string, ...interface{}) error
}, db, table, symbol string, t time.Time, o, h, l, c, v float64) error {
	insert := fmt.Sprintf("INSERT INTO %s.%s (s,t,o,h,l,c,v) VALUES (?, ?, ?, ?, ?, ?, ?)", db, table)
	return conn.Exec(ctx, insert, symbol, t.UTC(), o, h, l, c, v)
}
