package config

import (
	"os"
	"sync"
)

type Config struct {
	APPPort            string
	Urldatabase        string
	Databasename       string
	Userdatabase       string
	Passworddatabase   string
	AuthenHost         string
	KafkaBootrapServer string
	KafkaTopic         string
	KafkaGroupID       string
	ClickHouseHost     string
	ClickHousePort     string
	ClickHouseUser     string
	ClickHousePassword string
	ClickHouseDatabase string
	ClickHouseTable    string
}

func (c Config) String() string {
	//TODO implement me
	return "Config{APPPort:" + c.APPPort + ", Urldatabase:" + c.Urldatabase + ", Databasename:" + c.Databasename + ", Userdatabase:" + c.Userdatabase + ", Passworddatabase:" + c.Passworddatabase + ", AuthenHost:" + c.AuthenHost + ", KafkaBootrapServer:" + c.KafkaBootrapServer + ", KafkaTopic:" + c.KafkaTopic + ", KafkaGroupID:" + c.KafkaGroupID + ", ClickHouseHost:" + c.ClickHouseHost + ", ClickHousePort:" + c.ClickHousePort + ", ClickHouseUser:" + c.ClickHouseUser + ", ClickHousePassword:" + c.ClickHousePassword + ", ClickHouseDatabase:" + c.ClickHouseDatabase + ", ClickHouseTable:" + c.ClickHouseTable + "}"
}

var (
	Cfg  *Config
	once sync.Once
)

func LoadConfig() *Config {
	once.Do(func() {
		Cfg = &Config{
			APPPort:            os.Getenv("APP_PORT"),
			Urldatabase:        os.Getenv("URLDATABASE"),
			Databasename:       os.Getenv("DATABASENAME"),
			Userdatabase:       os.Getenv("USERDATABASE"),
			Passworddatabase:   os.Getenv("PASSWORDDATABASE"),
			AuthenHost:         os.Getenv("AUTHTHEN_HOST"),
			KafkaBootrapServer: os.Getenv("KAFKA_BOOTSTRAP_SERVERS"),
			KafkaTopic:         os.Getenv("KAFKA_TOPIC"),
			KafkaGroupID:       os.Getenv("KAFKA_GROUP_ID"),
			ClickHouseHost:     os.Getenv("CLICKHOUSE_HOST"),
			ClickHousePort:     os.Getenv("CLICKHOUSE_PORT"),
			ClickHouseUser:     os.Getenv("CLICKHOUSE_USER"),
			ClickHousePassword: os.Getenv("CLICKHOUSE_PASSWORD"),
			ClickHouseDatabase: os.Getenv("CLICKHOUSE_DATABASE"),
			ClickHouseTable:    os.Getenv("CLICKHOUSE_TABLE"),
		}
	})
	return Cfg
}
