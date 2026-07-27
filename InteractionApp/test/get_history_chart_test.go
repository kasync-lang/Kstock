package test

import (
	"Kstock/internal/handle"
	"Kstock/internal/server"
	"context"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/joho/godotenv"
)

func TestHistoryChart(t *testing.T) {
	cwd, _ := os.Getwd()
	err := godotenv.Load("../.env")
	fmt.Println(cwd)
	if err != nil {
		t.Fatal("Error loading .env file")
	}
	gin.SetMode(gin.TestMode)
	router := gin.New()
	ctx := context.Background()
	server.StartServer(ctx)
	router.GET("/history", handle.GetHistoryChart)
	fromtime := time.Date(2026, 7, 20, 0, 0, 0, 0, time.UTC)
	totime := time.Date(2026, 7, 23, 0, 0, 0, 0, time.UTC)
	req := httptest.NewRequest(
		http.MethodGet,
		fmt.Sprintf("/history?symbol=IBM&from=%d&to=%d&resolution=1D", fromtime.Unix(), totime.Unix()),
		nil,
	)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Errorf("Expected status %d, got %d", http.StatusOK, w.Code)
	}
	expected := `{"id":	"123"}`
	if w.Body.String() != expected {
		t.Errorf("Expected body %s, got %s", expected, w.Body.String())
	}
}
