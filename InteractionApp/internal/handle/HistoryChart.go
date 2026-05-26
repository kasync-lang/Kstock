package handle

import (
	"Kstock/internal/config"
	"Kstock/internal/server"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/gin-gonic/gin"
)

type historyResponse struct {
	S string    `json:"s"`
	T []int64   `json:"t"`
	O []float64 `json:"o"`
	H []float64 `json:"h"`
	L []float64 `json:"l"`
	C []float64 `json:"c"`
	V []float64 `json:"v"`
}

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

	interval, ok := resolutionToInterval(resolution)
	if !ok {
		c.JSON(http.StatusBadRequest, gin.H{"error": "unsupported resolution"})
		return
	}

	if config.Cfg == nil {
		config.LoadConfig()
	}
	if config.Cfg == nil || config.Cfg.ClickHouseDatabase == "" {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "clickhouse config not loaded"})
		return
	}

	conn := server.GetClickHouse()
	if conn == nil {
		if _, err := server.InitClickHouse(); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "clickhouse not initialized"})
			return
		}
		conn = server.GetClickHouse()
	}

	table := config.Cfg.ClickHouseTable
	if table == "" {
		table = "price_history"
	}

	query := fmt.Sprintf(`
SELECT
	toStartOfInterval(toDateTime(t), INTERVAL %s) AS bucket,
	argMin(p, t) AS open,
	max(p) AS high,
	min(p) AS low,
	argMax(p, t) AS close,
	sum(v) AS volume
FROM %s.%s
WHERE s = ? AND toDateTime(t) >= ? AND toDateTime(t) <= ?
GROUP BY bucket
ORDER BY bucket`, interval, config.Cfg.ClickHouseDatabase, table)

	rows, err := conn.Query(c.Request.Context(), query, symbol, time.Unix(fromUnix, 0).UTC(), time.Unix(toUnix, 0).UTC())
	if err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": "query clickhouse failed"})
		return
	}
	defer rows.Close()

	resp := historyResponse{S: "ok"}
	for rows.Next() {
		var bucket time.Time
		var open, high, low, closePrice, volume float64
		if err := rows.Scan(&bucket, &open, &high, &low, &closePrice, &volume); err != nil {
			c.JSON(http.StatusInternalServerError, gin.H{"error": "scan clickhouse rows failed"})
			return
		}
		resp.T = append(resp.T, bucket.UTC().Unix())
		resp.O = append(resp.O, open)
		resp.H = append(resp.H, high)
		resp.L = append(resp.L, low)
		resp.C = append(resp.C, closePrice)
		resp.V = append(resp.V, volume)
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
	case "30", "30m":
		return "30 MINUTE", true
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
