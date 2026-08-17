package test

import (
	"Kstock/internal/handle"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gin-gonic/gin"
)

func TestHistoryChartRequiresSymbolAndFrom(t *testing.T) {
	gin.SetMode(gin.TestMode)
	router := gin.New()
	router.GET("/history", handle.GetHistoryChart)
	req := httptest.NewRequest(http.MethodGet, "/history?symbol=IBM", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusBadRequest {
		t.Errorf("expected status %d, got %d", http.StatusBadRequest, w.Code)
	}
}
