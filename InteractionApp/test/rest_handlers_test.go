package test

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"Kstock/internal/dto"
	"Kstock/internal/handle"
	"github.com/DATA-DOG/go-sqlmock"
	"github.com/gin-gonic/gin"
)

type symbolsResponse struct {
	Data []dto.SymbolPublic `json:"data"`
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


