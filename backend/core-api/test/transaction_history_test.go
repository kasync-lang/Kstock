package test

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"Kstock/internal/dto"
	"Kstock/internal/handle"

	"github.com/DATA-DOG/go-sqlmock"
	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
)

func TestTransactionHistoryHandleOK(t *testing.T) {
	gin.SetMode(gin.TestMode)
	mock := setupMockDB(t)

	// page=2 => LIMIT 50, OFFSET 50
	mock.ExpectQuery(`SELECT COUNT\(\*\) FROM transaction WHERE user_id = \$1`).
		WithArgs("user-123").
		WillReturnRows(
			sqlmock.NewRows([]string{"count"}).
				AddRow(75),
		)

	transactedAt := time.Date(2026, 8, 20, 10, 30, 0, 0, time.UTC)
	rows := sqlmock.NewRows([]string{
		"id",
		"amount",
		"symbol",
		"operation",
		"price",
		"time_transacted",
	}).AddRow(
		"9a143e8a-3e40-48ad-956c-45ca5ea89391",
		10,
		"AAPL",
		"BUY",
		211.25,
		transactedAt,
	)

	mock.ExpectQuery(
		`(?s)SELECT id, amount, symbol, operation, price, time_transacted.*`+
			`FROM transaction.*`+
			`WHERE user_id = \$1.*`+
			`ORDER BY time_transacted DESC, id DESC.*`+
			`LIMIT \$2 OFFSET \$3`,
	).
		WithArgs("user-123", 50, 50).
		WillReturnRows(rows)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Request = httptest.NewRequest(
		http.MethodGet,
		"/api/transactions/history?page=2",
		nil,
	)
	c.Set("claims", jwt.MapClaims{
		"sub": "user-123",
	})

	handle.TransactionHistoryHandle(c)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status %d, got %d; response=%s",
			http.StatusOK, w.Code, w.Body.String())
	}

	var response dto.TransactionHistoryResponse
	if err := json.NewDecoder(w.Body).Decode(&response); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	if response.Page != 2 {
		t.Errorf("expected page=2, got %d", response.Page)
	}

	if response.PageSize != 50 {
		t.Errorf("expected page_size=50, got %d", response.PageSize)
	}

	if response.Total != 75 {
		t.Errorf("expected total=75, got %d", response.Total)
	}

	if response.TotalPages != 2 {
		t.Errorf("expected total_pages=2, got %d", response.TotalPages)
	}

	if response.HasNext {
		t.Error("expected has_next=false on the final page")
	}

	if len(response.Data) != 1 {
		t.Fatalf("expected 1 transaction, got %d", len(response.Data))
	}

	transaction := response.Data[0]
	if transaction.ID != "9a143e8a-3e40-48ad-956c-45ca5ea89391" {
		t.Errorf("unexpected transaction ID: %s", transaction.ID)
	}
	if transaction.Symbol != "AAPL" {
		t.Errorf("expected symbol AAPL, got %s", transaction.Symbol)
	}
	if transaction.Operation != "BUY" {
		t.Errorf("expected operation BUY, got %s", transaction.Operation)
	}
	if transaction.Amount != 10 {
		t.Errorf("expected amount=10, got %d", transaction.Amount)
	}
	if transaction.Price != 211.25 {
		t.Errorf("expected price=211.25, got %f", transaction.Price)
	}
	if !transaction.TimeTransacted.Equal(transactedAt) {
		t.Errorf(
			"expected time_transacted=%s, got %s",
			transactedAt,
			transaction.TimeTransacted,
		)
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Fatalf("unmet SQL mock expectations: %v", err)
	}
}

func TestTransactionHistoryHandleEmptyFirstPage(t *testing.T) {
	gin.SetMode(gin.TestMode)
	mock := setupMockDB(t)

	mock.ExpectQuery(`SELECT COUNT\(\*\) FROM transaction WHERE user_id = \$1`).
		WithArgs("user-without-history").
		WillReturnRows(
			sqlmock.NewRows([]string{"count"}).
				AddRow(0),
		)

	mock.ExpectQuery(
		`(?s)SELECT id, amount, symbol, operation, price, time_transacted.*`+
			`FROM transaction.*`+
			`WHERE user_id = \$1.*`+
			`ORDER BY time_transacted DESC, id DESC.*`+
			`LIMIT \$2 OFFSET \$3`,
	).
		WithArgs("user-without-history", 50, 0).
		WillReturnRows(
			sqlmock.NewRows([]string{
				"id",
				"amount",
				"symbol",
				"operation",
				"price",
				"time_transacted",
			}),
		)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Request = httptest.NewRequest(
		http.MethodGet,
		"/api/transactions/history",
		nil,
	)
	c.Set("claims", jwt.MapClaims{
		"sub": "user-without-history",
	})

	handle.TransactionHistoryHandle(c)

	if w.Code != http.StatusOK {
		t.Fatalf("expected status %d, got %d; response=%s",
			http.StatusOK, w.Code, w.Body.String())
	}

	var response dto.TransactionHistoryResponse
	if err := json.NewDecoder(w.Body).Decode(&response); err != nil {
		t.Fatalf("failed to decode response: %v", err)
	}

	if response.Page != 1 {
		t.Errorf("expected default page=1, got %d", response.Page)
	}
	if response.PageSize != 50 {
		t.Errorf("expected page_size=50, got %d", response.PageSize)
	}
	if response.Total != 0 {
		t.Errorf("expected total=0, got %d", response.Total)
	}
	if response.TotalPages != 0 {
		t.Errorf("expected total_pages=0, got %d", response.TotalPages)
	}
	if response.HasNext {
		t.Error("expected has_next=false for empty history")
	}
	if response.Data == nil {
		t.Error("expected data to be an empty JSON array ([]), not null")
	}
	if len(response.Data) != 0 {
		t.Errorf("expected no transactions, got %d", len(response.Data))
	}

	if err := mock.ExpectationsWereMet(); err != nil {
		t.Fatalf("unmet SQL mock expectations: %v", err)
	}
}

func TestTransactionHistoryHandleInvalidPage(t *testing.T) {
	gin.SetMode(gin.TestMode)

	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Request = httptest.NewRequest(
		http.MethodGet,
		"/api/transactions/history?page=0",
		nil,
	)
	c.Set("claims", jwt.MapClaims{
		"sub": "user-123",
	})

	handle.TransactionHistoryHandle(c)

	if w.Code != http.StatusBadRequest {
		t.Fatalf("expected status %d, got %d; response=%s",
			http.StatusBadRequest, w.Code, w.Body.String())
	}

	var response map[string]string
	if err := json.NewDecoder(w.Body).Decode(&response); err != nil {
		t.Fatalf("failed to decode error response: %v", err)
	}

	if response["error"] != "page must be a positive integer" {
		t.Errorf("unexpected error message: %q", response["error"])
	}
}
