package handle

import (
	"bytes"
	"database/sql"
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
	mock.ExpectQuery(regexp.QuoteMeta("SELECT symbol, quantity, average_price FROM assets WHERE user_id = $1")).WithArgs("user-1").WillReturnRows(sqlmock.NewRows([]string{"symbol", "quantity", "average_price"}).AddRow("AAPL", 2, 100.0))
	mock.ExpectQuery(regexp.QuoteMeta("SELECT COALESCE(amount, 0) FROM cash WHERE user_id = $1")).WithArgs("user-1").WillReturnRows(sqlmock.NewRows([]string{"amount"}).AddRow(125.5))
	store := dto.NewPriceStore()
	store.Update("AAPL", 125)
	c, w := handlerContext(http.MethodGet, "/assets", nil, true)
	c.Set("price_store", store)
	GetAsset(c)
	if w.Code != http.StatusOK {
		t.Fatalf("asset status = %d: %s", w.Code, w.Body.String())
	}
	var assets dto.Assets
	if err := json.Unmarshal(w.Body.Bytes(), &assets); err != nil || len(assets.Data) != 1 || assets.Data[0].ProfitAndLoss != 50 || assets.AllProfitAndLoss != 50 || assets.CashBalance != 125.5 {
		t.Fatalf("assets=%+v err=%v", assets, err)
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Fatal(err)
	}

	mock = setupDB(t)
	mock.ExpectQuery(regexp.QuoteMeta("SELECT symbol, quantity, average_price FROM assets WHERE user_id = $1")).WithArgs("user-1").WillReturnRows(sqlmock.NewRows([]string{"symbol", "quantity", "average_price"}).AddRow("MSFT", 1, 100.0))
	c, w = handlerContext(http.MethodGet, "/assets", nil, true)
	c.Set("price_store", dto.NewPriceStore())
	GetAsset(c)
	if w.Code != http.StatusInternalServerError {
		t.Fatalf("missing price status = %d", w.Code)
	}

	mock = setupDB(t)
	mock.ExpectQuery(regexp.QuoteMeta("SELECT symbol, quantity, average_price FROM assets WHERE user_id = $1")).WithArgs("user-1").WillReturnRows(sqlmock.NewRows([]string{"symbol", "quantity", "average_price"}))
	mock.ExpectQuery(regexp.QuoteMeta("SELECT COALESCE(amount, 0) FROM cash WHERE user_id = $1")).WithArgs("user-1").WillReturnRows(sqlmock.NewRows([]string{"amount"}).AddRow(0))
	c, w = handlerContext(http.MethodGet, "/assets", nil, true)
	c.Set("price_store", dto.NewPriceStore())
	GetAsset(c)
	if w.Code != http.StatusOK {
		t.Fatalf("empty assets status = %d: %s", w.Code, w.Body.String())
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Fatal(err)
	}
}

func TestGetCashBalance(t *testing.T) {
	c, w := handlerContext(http.MethodGet, "/assets/cash", nil, false)
	GetCashBalance(c)
	if w.Code != http.StatusUnauthorized {
		t.Fatalf("missing claims status = %d", w.Code)
	}

	mock := setupDB(t)
	mock.ExpectQuery(regexp.QuoteMeta("SELECT COALESCE(amount, 0) FROM cash WHERE user_id = $1")).WithArgs("user-1").WillReturnRows(sqlmock.NewRows([]string{"amount"}).AddRow(125.5))
	c, w = handlerContext(http.MethodGet, "/assets/cash", nil, true)
	GetCashBalance(c)
	if w.Code != http.StatusOK {
		t.Fatalf("cash balance status = %d: %s", w.Code, w.Body.String())
	}
	var response dto.CashBalanceResponse
	if err := json.Unmarshal(w.Body.Bytes(), &response); err != nil || response.CashBalance != 125.5 {
		t.Fatalf("response=%+v err=%v", response, err)
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Fatal(err)
	}

	mock = setupDB(t)
	mock.ExpectQuery(regexp.QuoteMeta("SELECT COALESCE(amount, 0) FROM cash WHERE user_id = $1")).WithArgs("user-1").WillReturnError(sql.ErrNoRows)
	c, w = handlerContext(http.MethodGet, "/assets/cash", nil, true)
	GetCashBalance(c)
	if w.Code != http.StatusOK {
		t.Fatalf("missing cash row status = %d: %s", w.Code, w.Body.String())
	}
	if err := json.Unmarshal(w.Body.Bytes(), &response); err != nil || response.CashBalance != 0 {
		t.Fatalf("response=%+v err=%v", response, err)
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
		INSERT INTO cash (user_id, amount)
		VALUES ($1, $2)
		ON CONFLICT (user_id)
		DO UPDATE SET amount = cash.amount + EXCLUDED.amount
		RETURNING amount
	`)).WithArgs("user-1", 25.5).WillReturnRows(sqlmock.NewRows([]string{"amount"}).AddRow(125.5))
	c, w = handlerContext(http.MethodPost, "/assets/topup", []byte(`{"amount":25.5}`), true)
	Topup(c)
	if w.Code != http.StatusOK {
		t.Fatalf("top-up status = %d: %s", w.Code, w.Body.String())
	}
	var response dto.TopupResponse
	if err := json.Unmarshal(w.Body.Bytes(), &response); err != nil || response.Amount != 25.5 || response.NewCashBalance != 125.5 {
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
	mock.ExpectExec(regexp.QuoteMeta("INSERT INTO cash (user_id, amount) VALUES ($1, 0) ON CONFLICT (user_id) DO NOTHING")).WithArgs("user-1").WillReturnResult(sqlmock.NewResult(1, 1))
	mock.ExpectQuery(regexp.QuoteMeta("SELECT COALESCE(amount, 0) FROM cash WHERE user_id = $1 FOR UPDATE")).WithArgs("user-1").WillReturnRows(sqlmock.NewRows([]string{"amount"}).AddRow(50.0))
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

func TestBuyTransactionUsesDedicatedCashBalance(t *testing.T) {
	mock := setupDB(t)
	mock.ExpectBegin()
	mock.ExpectExec(regexp.QuoteMeta("INSERT INTO cash (user_id, amount) VALUES ($1, 0) ON CONFLICT (user_id) DO NOTHING")).WithArgs("user-1").WillReturnResult(sqlmock.NewResult(1, 1))
	mock.ExpectQuery(regexp.QuoteMeta("SELECT COALESCE(amount, 0) FROM cash WHERE user_id = $1 FOR UPDATE")).WithArgs("user-1").WillReturnRows(sqlmock.NewRows([]string{"amount"}).AddRow(100.0))
	mock.ExpectQuery(regexp.QuoteMeta("SELECT quantity, average_price FROM assets WHERE user_id = $1 AND symbol = $2 FOR UPDATE")).WithArgs("user-1", "AAPL").WillReturnError(sql.ErrNoRows)
	mock.ExpectExec(regexp.QuoteMeta("UPDATE cash SET amount = $1 WHERE user_id = $2")).WithArgs(80.0, "user-1").WillReturnResult(sqlmock.NewResult(1, 1))
	mock.ExpectExec(regexp.QuoteMeta(`
		INSERT INTO assets (user_id, symbol, quantity, average_price)
		VALUES ($1, $2, $3, $4)
		ON CONFLICT (user_id, symbol)
		DO UPDATE SET quantity = EXCLUDED.quantity, average_price = EXCLUDED.average_price
	`)).WithArgs("user-1", "AAPL", 2, 10.0).WillReturnResult(sqlmock.NewResult(1, 1))
	mock.ExpectExec(regexp.QuoteMeta(`
		INSERT INTO transaction (user_id, amount, symbol, operation, price)
		VALUES ($1, $2, $3, $4, $5)
	`)).WithArgs("user-1", 2, "AAPL", "BUY", 10.0).WillReturnResult(sqlmock.NewResult(1, 1))
	mock.ExpectCommit()

	c, w := handlerContext(http.MethodPost, "/transactions", []byte(`{"operation":"buy","symbol":"aapl","quantity":2}`), true)
	store := dto.NewPriceStore()
	store.Update("AAPL", 10)
	c.Set("price_store", store)
	TransactionHandle(c)

	if w.Code != http.StatusOK {
		t.Fatalf("buy status = %d: %s", w.Code, w.Body.String())
	}
	var response dto.BuyOrderResponse
	if err := json.Unmarshal(w.Body.Bytes(), &response); err != nil || response.NewCashBalance != 80 || response.TotalHoldings != 2 || response.NewUnitPrice != 10 {
		t.Fatalf("response=%+v err=%v", response, err)
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
