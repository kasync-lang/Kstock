package dto

type SymbolBaseDetail struct {
	Country              string  `json:"country" db:"country"`
	Currency             string  `json:"currency" db:"currency"`
	Exhange              string  `json:"exchange" db:"exchange"`
	IPO                  string  `json:"ipo" db:"ipo"`
	MarketCapitalization float64 `json:"marketCapitalization" db:"market_capitalization"`
	Phone                string  `json:"phone" db:"phone"`
	ShareOutstanding     float64 `json:"shareOutstanding" db:"share_outstanding"`
	Website              string  `json:"weburl" db:"weburl"`
	Industry             string  `json:"industry" db:"finnhub_industry"`
	SymbolPublic
}
type SymbolPublic struct {
	Ticker string `json:"ticker" db:"ticker"`
	Name   string `json:"name" db:"name"`
	Logo   string `json:"logo" db:"logo"`
}
type SymbolPreview struct {
	SymbolPublic
	LastPrice     float64 `json:"lastPrice"`
	PercentChange float64 `json:"percentChange"`
}
type QuerySymbol struct {
	Name    string `form:"name" binding:"omitempty" default:""`
	Exhange string `form:"exchange" binding:"omitempty" default:"NASDAQ"`
	OrderBy string `form:"order_by" binding:"omitempty" oneof:"name,market_cap,ipo" default:"name"`
}
