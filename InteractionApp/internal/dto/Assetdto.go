package dto

type Asset struct {
	Symbol   string  `json:"symbol" db:"symbol"`
	Quantity float64 `json:"quantity" db:"quantity"`
	Price    float64 `json:"price" db:"unit_price"`
}
type Assets struct {
	Data []Asset `json:"data" db:"_"`
}

type Order struct {
	Symbol    string `json:"symbol" db:"symbol"`
	Quantity  int    `json:"quantity" db:"quantity"`
	Operation string `json:"operation" db:"operation"`
}
