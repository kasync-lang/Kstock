package dto

type Trigger struct {
	Operator  string   `json:"operator" db:"operator"`
	Threshold *float64 `json:"threshold" db:"threshold" `
	Indicator string   `json:"indicator" db:"indicator"`
}
type AlertBase struct {
	Symbol string `json:"symbol" db:"symbol"`
	Active bool   `json:"active" db:"active" default:"true"`
}
type AlertDetail struct {
	AlertBase
	ID        int       `json:"id" db:"alert_id"`
	CreatedAt string    `json:"created_at" db:"created_at"`
	UpdatedAt string    `json:"updated_at" db:"updated_at"`
	Triggers  []Trigger `json:"triggers" db:"_"`
}
type AlertCreate struct {
	AlertBase
	Triggers *[]Trigger `json:"triggers" db:"_"`
}
type AlertUpdate struct {
	ID       int        `json:"id" db:"alert_id"`
	Active   *bool      `json:"active" db:"active"`
	Triggers *[]Trigger `json:"triggers" db:"_"`
}
