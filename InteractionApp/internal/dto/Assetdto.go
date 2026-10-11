package dto

type Asset struct {
	Symbol        string  `json:"symbol" db:"symbol"`
	Quantity      float64 `json:"quantity" db:"quantity"`
	Price         float64 `json:"price" db:"unit_price"`
	ProfitAndLoss float64 `json:"profit_and_loss"`
	MarketValue   float64 `json:"market_value"`
}
type Assets struct {
	Data             []Asset `json:"data" db:"_"`
	AllProfitAndLoss float64 `json:"all_profit_and_loss"`
	CashBalance      float64 `json:"cash_balance"`
}

type CashBalanceResponse struct {
	CashBalance float64 `json:"cash_balance"`
}

type TopupRequest struct {
	Amount float64 `json:"amount" binding:"required,gt=0"`
}

type TopupResponse struct {
	Message        string  `json:"message"`
	Amount         float64 `json:"amount"`
	NewCashBalance float64 `json:"new_cash_balance"`
}
