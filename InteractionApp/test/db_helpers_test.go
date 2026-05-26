package test

import (
	"testing"

	"Kstock/internal/server"

	"github.com/DATA-DOG/go-sqlmock"
	"github.com/jmoiron/sqlx"
)

func setupMockDB(t *testing.T) sqlmock.Sqlmock {
	t.Helper()
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatalf("sqlmock.New error: %v", err)
	}
	server.SetDBForTest(sqlx.NewDb(db, "sqlmock"))
	t.Cleanup(func() {
		server.ResetDBForTest()
		_ = db.Close()
	})
	return mock
}


