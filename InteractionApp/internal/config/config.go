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
}

func (c Config) String() string {
	//TODO implement me
	return "Config{APPPort:" + c.APPPort + ", Urldatabase:" + c.Urldatabase + ", Databasename:" + c.Databasename + ", Userdatabase:" + c.Userdatabase + ", Passworddatabase:" + c.Passworddatabase + ", AuthenHost:" + c.AuthenHost + "}"
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
			KafkaGroupID:       os.Getenv("KAFKA_GROUP_ID")}
	})
	return Cfg
}
