package test

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"Kstock/internal/dto"
	"Kstock/internal/handle"
	"Kstock/internal/server"
	"github.com/DATA-DOG/go-sqlmock"
	"github.com/gin-gonic/gin"
)

type symbolsResponse struct {
	Data []dto.SymbolPreview `json:"data"`
}

type symbolDetailResponse struct {
	Data dto.SymbolBaseDetail `json:"data"`
}

func TestGetSymbolsOK(t *testing.T) {
	gin.SetMode(gin.TestMode)
	mock := setupMockDB(t)

	queryRegex := `(?s)SELECT name, ticker, logo.*ORDER BY ticker`
	rows := sqlmock.NewRows([]string{"name", "ticker", "logo"}).
		AddRow("Apple Inc", "AAPL", "logo1").
		AddRow("Amazon", "AMZN", "logo2")
	mock.ExpectQuery(queryRegex).
		WithArgs("AP%", "NAS%").
		WillReturnRows(rows)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Request = httptest.NewRequest(http.MethodGet, "/api/symbols?name=ap&exchange=NAS&order_by=unknown", nil)

	handle.GetSymbols(c)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", w.Code)
	}

	var resp symbolsResponse
	if err := json.NewDecoder(w.Body).Decode(&resp); err != nil {
		t.Fatalf("decode response error: %v", err)
	}
	if len(resp.Data) != 2 {
		t.Fatalf("expected 2 symbols, got %d", len(resp.Data))
	}
	if resp.Data[0].Ticker != "AAPL" {
		t.Fatalf("expected ticker AAPL, got %s", resp.Data[0].Ticker)
	}
	if resp.Data[0].LastPrice != 0 || resp.Data[0].PercentChange != 0 {
		t.Fatalf("expected zero price fields without ClickHouse history, got lastPrice=%v percentChange=%v", resp.Data[0].LastPrice, resp.Data[0].PercentChange)
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Fatalf("sqlmock expectations: %v", err)
	}
}

func TestGetSymbolDetailOK(t *testing.T) {
	gin.SetMode(gin.TestMode)
	mock := setupMockDB(t)

	queryRegex := `SELECT \* FROM company_profile WHERE ticker=\$1`
	rows := sqlmock.NewRows([]string{
		"country",
		"currency",
		"exchange",
		"ipo",
		"market_capitalization",
		"name",
		"phone",
		"share_outstanding",
		"ticker",
		"weburl",
		"logo",
		"finnhub_industry",
	}).AddRow(
		"US",
		"USD",
		"NASDAQ",
		"1980-12-12",
		123456.78,
		"Apple Inc",
		"123456",
		1000.5,
		"AAPL",
		"https://apple.com",
		"logo1",
		"Technology",
	)
	mock.ExpectQuery(queryRegex).
		WithArgs("AAPL").
		WillReturnRows(rows)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Params = gin.Params{{Key: "symbol", Value: "AAPL"}}
	c.Request = httptest.NewRequest(http.MethodGet, "/api/symbols/AAPL/detail", nil)

	handle.GetSymbolDetail(c)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", w.Code)
	}

	var resp symbolDetailResponse
	if err := json.NewDecoder(w.Body).Decode(&resp); err != nil {
		t.Fatalf("decode response error: %v", err)
	}
	if resp.Data.Ticker != "AAPL" {
		t.Fatalf("expected ticker AAPL, got %s", resp.Data.Ticker)
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Fatalf("sqlmock expectations: %v", err)
	}
}

func TestGetSymbolsWithCachedPriceAndPagination(t *testing.T) {
	gin.SetMode(gin.TestMode)
	mock := setupMockDB(t)

	// Populate DailyCloseStore
	dailyStore := server.GetDailyCloseStore()
	dailyStore.ReplaceAll(map[string]dto.DailyClose{
		"AAPL": {
			Last:    150.0,
			Prev:    100.0,
			HasLast: true,
			HasPrev: true,
		},
		"AMZN": {
			Last:    200.0,
			Prev:    200.0,
			HasLast: true,
			HasPrev: true,
		},
	})
	t.Cleanup(func() {
		dailyStore.ReplaceAll(nil)
	})

	queryRegex := `(?s)SELECT name, ticker, logo.*LIMIT \$3 OFFSET \$4`
	rows := sqlmock.NewRows([]string{"name", "ticker", "logo"}).
		AddRow("Apple Inc", "AAPL", "logo1").
		AddRow("Amazon", "AMZN", "logo2")
	mock.ExpectQuery(queryRegex).
		WithArgs("AP%", "NAS%", 10, 20).
		WillReturnRows(rows)

	// PriceStore with live price for AAPL
	priceStore := dto.NewPriceStore()
	priceStore.Update("AAPL", 160.0) // live price is 160, prev close is 100 -> change should be +60%

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Set("price_store", priceStore)
	c.Request = httptest.NewRequest(http.MethodGet, "/api/symbols?name=ap&exchange=NAS&order_by=unknown&limit=10&offset=20", nil)

	handle.GetSymbols(c)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", w.Code)
	}

	var resp symbolsResponse
	if err := json.NewDecoder(w.Body).Decode(&resp); err != nil {
		t.Fatalf("decode response error: %v", err)
	}
	if len(resp.Data) != 2 {
		t.Fatalf("expected 2 symbols, got %d", len(resp.Data))
	}

	// AAPL: live price 160.0, change (160 - 100) / 100 * 100 = 60.0%
	if resp.Data[0].Ticker != "AAPL" {
		t.Fatalf("expected ticker AAPL, got %s", resp.Data[0].Ticker)
	}
	if resp.Data[0].LastPrice != 160.0 {
		t.Fatalf("expected lastPrice 160.0, got %v", resp.Data[0].LastPrice)
	}
	if resp.Data[0].PercentChange != 60.0 {
		t.Fatalf("expected percentChange 60.0, got %v", resp.Data[0].PercentChange)
	}

	// AMZN: no live price, cached last 200.0, prev 200.0 -> change 0.0%
	if resp.Data[1].Ticker != "AMZN" {
		t.Fatalf("expected ticker AMZN, got %s", resp.Data[1].Ticker)
	}
	if resp.Data[1].LastPrice != 200.0 {
		t.Fatalf("expected lastPrice 200.0, got %v", resp.Data[1].LastPrice)
	}
	if resp.Data[1].PercentChange != 0.0 {
		t.Fatalf("expected percentChange 0.0, got %v", resp.Data[1].PercentChange)
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Fatalf("sqlmock expectations: %v", err)
	}
}

