package server

import (
	"Kstock/internal/config"
	"fmt"
	"github.com/jmoiron/sqlx"
	_ "github.com/lib/pq"
	"sync"
)

var (
	instance *sqlx.DB
	once     sync.Once
)

func IntiDB() (*sqlx.DB, error) {
	var err error
	once.Do(func() {
		dsn := fmt.Sprintf("host=%s user=%s password=%s dbname=%s sslmode=disable connect_timeout=5", config.Cfg.Urldatabase, config.Cfg.Userdatabase, config.Cfg.Passworddatabase, config.Cfg.Databasename)
		instance, err = sqlx.Connect("postgres", dsn)
		if err != nil {
			return
		}
		if err = instance.Ping(); err != nil {
			instance = nil
		}
	})

	return instance, err
}
func GetDB() *sqlx.DB {
	return instance
}
