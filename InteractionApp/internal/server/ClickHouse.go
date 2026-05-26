package server

import (
	"Kstock/internal/config"
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/ClickHouse/clickhouse-go/v2"
)

var (
	clickhouseConn clickhouse.Conn
	clickhouseOnce sync.Once
)

func InitClickHouse() (clickhouse.Conn, error) {
	var err error
	clickhouseOnce.Do(func() {
		if config.Cfg == nil {
			config.LoadConfig()
		}
		if config.Cfg == nil {
			err = fmt.Errorf("clickhouse config is nil")
			return
		}
		addr := fmt.Sprintf("%s:%s", config.Cfg.ClickHouseHost, config.Cfg.ClickHousePort)
		conn, openErr := clickhouse.Open(&clickhouse.Options{
			Addr: []string{addr},
			Auth: clickhouse.Auth{
				Database: config.Cfg.ClickHouseDatabase,
				Username: config.Cfg.ClickHouseUser,
				Password: config.Cfg.ClickHousePassword,
			},
			DialTimeout: time.Second * 5,
		})
		if openErr != nil {
			err = openErr
			return
		}
		err = conn.Ping(context.Background())
		if err != nil {
			return
		}
		clickhouseConn = conn
	})

	return clickhouseConn, err
}

func GetClickHouse() clickhouse.Conn {
	return clickhouseConn
}
