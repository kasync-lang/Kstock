package test

import (
	"Kstock/internal/handle"
	"net/http"
	"net/http/httptest"
	"regexp"
	"testing"

	"github.com/DATA-DOG/go-sqlmock"
	"github.com/gin-gonic/gin"
)

func TestGetSymbolsUsesSafeDefaultOrder(t *testing.T) {
	gin.SetMode(gin.TestMode)
	mock := setupMockDB(t)
	mock.ExpectQuery(regexp.MustCompile(`(?s)SELECT name, ticker, logo.*ORDER BY ticker`).String()).
		WithArgs("%", "%").
		WillReturnRows(sqlmock.NewRows([]string{"name", "ticker", "logo"}))
	router := gin.New()
	router.GET("/symbols", handle.GetSymbols)
	req := httptest.NewRequest(http.MethodGet, "/symbols?order_by=unexpected", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("expected status %d, got %d", http.StatusBadRequest, w.Code)
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Fatal(err)
	}
}
