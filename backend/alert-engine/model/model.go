package model

import "time"

const (
	LogicAnd = "AND"
	LogicOr  = "OR"
)

// Indicator names stored in triggeralert.indicator (see frontend AlertsPage.tsx).
const (
	IndicatorPrice  = "PRICE"
	IndicatorVolume = "VOLUME"
	IndicatorRSI    = "RSI"
)

// Tick is one trade from the raw_data_trade topic (same shape as core-api dto.Tick).
type Tick struct {
	C []string `json:"c"`
	P float64  `json:"p"`
	S string   `json:"s"`
	T int64    `json:"t"` // unix milliseconds
	V int      `json:"v"`
}

type Trigger struct {
	Indicator string  `json:"indicator" db:"indicator"`
	Operator  string  `json:"operator" db:"condition"`
	Threshold float64 `json:"threshold" db:"value"`
	Position  int     `json:"position" db:"position"`
}

// Alert is an active rule held in memory by the engine.
type Alert struct {
	ID       string    `json:"id"`
	UserID   string    `json:"user_id"`
	Symbol   string    `json:"symbol"`
	Logic    string    `json:"logic"`
	Triggers []Trigger `json:"triggers"`
}

// AlertTriggered is the payload published to the alert_triggered topic.
// HistoryID is the idempotency key for the notifier.
type AlertTriggered struct {
	HistoryID   string    `json:"history_id"`
	AlertID     string    `json:"alert_id"`
	UserID      string    `json:"user_id"`
	Symbol      string    `json:"symbol"`
	Price       float64   `json:"price"`
	Logic       string    `json:"logic"`
	Triggers    []Trigger `json:"triggers"`
	TriggeredAt time.Time `json:"triggered_at"`
}
