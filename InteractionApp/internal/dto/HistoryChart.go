package dto

import "time"

type HistoryResponse struct {
	S string    `json:"s"`
	T []int64   `json:"t"`
	O []float64 `json:"o"`
	H []float64 `json:"h"`
	L []float64 `json:"l"`
	C []float64 `json:"c"`
	V []float64 `json:"v"`
}
type Candle struct {
	Symbol    string    `db:"symbol"`
	Open      float64   `db:"open"`
	Close     float64   `db:"close"`
	High      float64   `db:"high"`
	Low       float64   `db:"low"`
	Volume    float64   `db:"volume"`
	Timestamp time.Time `db:"timestamp"`
}
