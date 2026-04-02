package dto

type BuyOrderResponse struct {
	Message       string  `json:"message"`
	Symbol        string  `json:"symbol"`
	Amount        int     `json:"amount"`
	Price         float64 `json:"price"`
	TotalCost     float64 `json:"total_cost"`
	NewUsdBalance float64 `json:"new_usd_balance"`
	NewUnitPrice  float64 `json:"new_unit_price"`
	TotalHoldings int     `json:"total_holdings"`
}
type Order struct {
	Symbol    string `json:"symbol" db:"symbol"`
	Quantity  int    `json:"quantity" db:"quantity"`
	Operation string `json:"operation" db:"operation"`
}
type SellOrderResponse struct {
	Message           string      `json:"message"`
	Symbol            string      `json:"symbol"`
	Amount            int         `json:"amount"`
	Price             float64     `json:"price"`
	TotalProceeds     interface{} `json:"total_proceeds"`
	NewUsdBalance     interface{} `json:"new_usd_balance"`
	RemainingHoldings interface{} `json:"remaining_holdings"`
}
