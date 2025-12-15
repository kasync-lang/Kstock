package dto

type SymbolBaseDetail struct {
	Country              string  `json:"country"`
	Currency             string  `json:"currency"`
	Exhange              string  `json:"exchange"`
	IPO                  string  `json:"ipo"`
	MarketCapitalization float64 `json:"marketCapitalization"`
	Name                 string  `json:"name"`
	Phone                string  `json:"phone"`
	ShareOutstanding     float64 `json:"shareOutstanding"`
	Ticker               string  `json:"ticker"`
	Website              string  `json:"weburl"`
	Logo                 string  `json:"logo"`
	Industry             string  `json:"industry"`
}
type SymbolPublic struct {
	Ticker string `json:"ticker" db:"ticker"`
	Name   string `json:"name" db:"name"`
	Logo   string `json:"logo" db:"logo"`
}
