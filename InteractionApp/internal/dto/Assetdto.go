package dto

type Asset struct {
	Symbol   string  `json:"symbol" db:"symbol"`
	Quantity float64 `json:"quantity" db:"quantity"`
	Price    float64 `json:"price" db:"unit_price"`
}
type Assets struct {
	Data []Asset `json:"data" db:"_"`
}
