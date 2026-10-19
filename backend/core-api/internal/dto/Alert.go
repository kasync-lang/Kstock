package dto

const (
	LogicAnd = "AND"
	LogicOr  = "OR"
)

type Trigger struct {
	Indicator string   `json:"indicator" db:"indicator"`
	Operator  string   `json:"operator" db:"condition"`
	Threshold *float64 `json:"threshold" db:"value"`
	Position  int      `json:"position" db:"position"`
}
type AlertBase struct {
	Symbol string `json:"symbol" db:"symbol"`
	Active bool   `json:"active" db:"status" default:"true"`
	Logic  string `json:"logic" db:"logic"`
}
type AlertDetail struct {
	AlertBase
	ID        string    `json:"id" db:"id"`
	CreatedAt string    `json:"created_at" db:"created_at"`
	UpdatedAt string    `json:"updated_at" db:"updated_at"`
	Triggers  []Trigger `json:"triggers" db:"-"`
}
type AlertCreate struct {
	AlertBase
	Triggers *[]Trigger `json:"triggers" db:"-"`
}
type AlertUpdate struct {
	ID       string     `json:"id" db:"id"`
	Active   *bool      `json:"active" db:"status"`
	Logic    *string    `json:"logic" db:"logic"`
	Triggers *[]Trigger `json:"triggers" db:"-"`
}
