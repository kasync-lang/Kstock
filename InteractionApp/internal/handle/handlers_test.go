package handle

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"regexp"
	"testing"

	"Kstock/internal/dto"
	"Kstock/internal/server"

	"github.com/DATA-DOG/go-sqlmock"
	"github.com/gin-gonic/gin"
	"github.com/golang-jwt/jwt/v5"
	"github.com/jmoiron/sqlx"
)

func setupDB(t *testing.T) sqlmock.Sqlmock {
	t.Helper()
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatal(err)
	}
	server.SetDBForTest(sqlx.NewDb(db, "sqlmock"))
	t.Cleanup(func() { server.ResetDBForTest(); _ = db.Close() })
	return mock
}

func handlerContext(method, target string, body []byte, claims bool) (*gin.Context, *httptest.ResponseRecorder) {
	gin.SetMode(gin.TestMode)
	w := httptest.NewRecorder()
	c, _ := gin.CreateTestContext(w)
	c.Request = httptest.NewRequest(method, target, bytes.NewReader(body))
	c.Request.Header.Set("Content-Type", "application/json")
	if claims {
		c.Set("claims", jwt.MapClaims{"sub": "user-1"})
	}
	return c, w
}

func TestFavoriteHandlersAuthorizationAndMutations(t *testing.T) {
	c, w := handlerContext(http.MethodGet, "/", nil, false)
	GetAllFavorite(c)
	if w.Code != http.StatusUnauthorized {
		t.Fatalf("missing claims status = %d", w.Code)
	}

	mock := setupDB(t)
	c, w = handlerContext(http.MethodPost, "/favorites/AAPL", nil, true)
	c.Params = gin.Params{{Key: "symbol", Value: "AAPL"}}
	mock.ExpectExec(regexp.QuoteMeta("insert into favorite_symbols (user_id, symbol) values ($1, $2) on conflict (user_id, symbol) do nothing")).WithArgs("user-1", "AAPL").WillReturnResult(sqlmock.NewResult(1, 1))
	AddFavorite(c)
	if w.Code != http.StatusOK {
		t.Fatalf("add status = %d", w.Code)
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Fatal(err)
	}
}

func TestNoteHandlers(t *testing.T) {
	c, w := handlerContext(http.MethodPost, "/notes", []byte("{"), true)
	CreateNote(c)
	if w.Code != http.StatusBadRequest {
		t.Fatalf("invalid body status = %d", w.Code)
	}

	mock := setupDB(t)
	mock.ExpectQuery(regexp.QuoteMeta("insert into note (user_id, symbol,title, content) values ($1, $2, $3, $4) returning note_id, title")).WithArgs("user-1", "AAPL", "Plan", "Buy later").WillReturnRows(sqlmock.NewRows([]string{"note_id", "title"}).AddRow("note-1", "Plan"))
	c, w = handlerContext(http.MethodPost, "/notes", []byte(`{"symbol":"AAPL","title":"Plan","content":"Buy later"}`), true)
	CreateNote(c)
	if w.Code != http.StatusOK {
		t.Fatalf("create status = %d body=%s", w.Code, w.Body.String())
	}
	var response struct {
		Data dto.NotePublic `json:"data"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &response); err != nil || response.Data.ID != "note-1" {
		t.Fatalf("response=%s err=%v", w.Body, err)
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Fatal(err)
	}
}

func TestCreateAlertRejectsMissingTriggers(t *testing.T) {
	c, w := handlerContext(http.MethodPost, "/alerts", []byte(`{"symbol":"AAPL","active":true}`), true)
	CreateAlert(c)
	if w.Code != http.StatusBadRequest {
		t.Fatalf("missing triggers status = %d", w.Code)
	}
}

func TestGetAssetCalculatesProfitAndHandlesMissingPrice(t *testing.T) {
	mock := setupDB(t)
	mock.ExpectQuery(regexp.QuoteMeta("select symbol, quantity, unit_price from assets where user_id = $1")).WithArgs("user-1").WillReturnRows(sqlmock.NewRows([]string{"symbol", "quantity", "unit_price"}).AddRow("AAPL", 2, 100.0))
	store := dto.NewPriceStore()
	store.Update("AAPL", 125)
	c, w := handlerContext(http.MethodGet, "/assets", nil, true)
	c.Set("price_store", store)
	GetAsset(c)
	if w.Code != http.StatusOK {
		t.Fatalf("asset status = %d: %s", w.Code, w.Body.String())
	}
	var assets dto.Assets
	if err := json.Unmarshal(w.Body.Bytes(), &assets); err != nil || len(assets.Data) != 1 || assets.Data[0].ProfitAndLoss != 50 || assets.AllProfitAndLoss != 50 {
		t.Fatalf("assets=%+v err=%v", assets, err)
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Fatal(err)
	}

	mock = setupDB(t)
	mock.ExpectQuery(regexp.QuoteMeta("select symbol, quantity, unit_price from assets where user_id = $1")).WithArgs("user-1").WillReturnRows(sqlmock.NewRows([]string{"symbol", "quantity", "unit_price"}).AddRow("MSFT", 1, 100.0))
	c, w = handlerContext(http.MethodGet, "/assets", nil, true)
	c.Set("price_store", dto.NewPriceStore())
	GetAsset(c)
	if w.Code != http.StatusInternalServerError {
		t.Fatalf("missing price status = %d", w.Code)
	}

	mock = setupDB(t)
	mock.ExpectQuery(regexp.QuoteMeta("select symbol, quantity, unit_price from assets where user_id = $1")).WithArgs("user-1").WillReturnRows(sqlmock.NewRows([]string{"symbol", "quantity", "unit_price"}).AddRow("USD", 125.5, 1.0))
	c, w = handlerContext(http.MethodGet, "/assets", nil, true)
	c.Set("price_store", dto.NewPriceStore())
	GetAsset(c)
	if w.Code != http.StatusOK {
		t.Fatalf("USD asset status = %d: %s", w.Code, w.Body.String())
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Fatal(err)
	}
}

func TestTopup(t *testing.T) {
	c, w := handlerContext(http.MethodPost, "/assets/topup", []byte(`{"amount":0}`), true)
	Topup(c)
	if w.Code != http.StatusBadRequest {
		t.Fatalf("invalid amount status = %d", w.Code)
	}

	c, w = handlerContext(http.MethodPost, "/assets/topup", []byte(`{"amount":25}`), false)
	Topup(c)
	if w.Code != http.StatusUnauthorized {
		t.Fatalf("missing claims status = %d", w.Code)
	}

	mock := setupDB(t)
	mock.ExpectQuery(regexp.QuoteMeta(`
		INSERT INTO assets (user_id, symbol, quantity, unit_price)
		VALUES ($1, 'USD', $2, 1)
		ON CONFLICT (user_id, symbol)
		DO UPDATE SET quantity = assets.quantity + EXCLUDED.quantity
		RETURNING quantity
	`)).WithArgs("user-1", 25.5).WillReturnRows(sqlmock.NewRows([]string{"quantity"}).AddRow(125.5))
	c, w = handlerContext(http.MethodPost, "/assets/topup", []byte(`{"amount":25.5}`), true)
	Topup(c)
	if w.Code != http.StatusOK {
		t.Fatalf("top-up status = %d: %s", w.Code, w.Body.String())
	}
	var response dto.TopupResponse
	if err := json.Unmarshal(w.Body.Bytes(), &response); err != nil || response.Amount != 25.5 || response.NewUSDBalance != 125.5 {
		t.Fatalf("response=%+v err=%v", response, err)
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Fatal(err)
	}
}

func TestTransactionValidationAndInsufficientBalance(t *testing.T) {
	c, w := handlerContext(http.MethodPost, "/transactions", []byte(`{"operation":"HOLD","symbol":"AAPL","quantity":1}`), true)
	store := dto.NewPriceStore()
	store.Update("AAPL", 100)
	c.Set("price_store", store)
	TransactionHandle(c)
	if w.Code != http.StatusBadRequest {
		t.Fatalf("invalid operation status = %d", w.Code)
	}

	mock := setupDB(t)
	mock.ExpectBegin()
	mock.ExpectQuery(regexp.QuoteMeta("SELECT COALESCE(quantity, 0) FROM assets WHERE user_id = $1 AND symbol = 'USD'")).WithArgs("user-1").WillReturnRows(sqlmock.NewRows([]string{"quantity"}).AddRow(50.0))
	mock.ExpectRollback()
	c, w = handlerContext(http.MethodPost, "/transactions", []byte(`{"operation":"BUY","symbol":"AAPL","quantity":1}`), true)
	c.Set("price_store", store)
	TransactionHandle(c)
	if w.Code != http.StatusForbidden {
		t.Fatalf("insufficient balance status = %d", w.Code)
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Fatal(err)
	}
}

func TestResolutionHelpers(t *testing.T) {
	if table, err := resolutionToTableName(" 1D "); err != nil || table != "ohlcv_1d" {
		t.Fatalf("table = %q, err=%v", table, err)
	}
	if _, err := resolutionToTableName("2h"); err == nil {
		t.Fatal("unsupported table resolution succeeded")
	}
	if interval, ok := resolutionToInterval("3h"); !ok || interval != "3 HOUR" {
		t.Fatalf("interval = %q, ok=%v", interval, ok)
	}
}
