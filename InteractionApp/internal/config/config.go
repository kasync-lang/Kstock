package config

import (
	"os"
	"sync"
)

type Config struct {
	APPPort          string
	Urldatabase      string
	Databasename     string
	Userdatabase     string
	Passworddatabase string
	AuthenHost       string
}

var (
	Cfg  *Config
	once sync.Once
)

func LoadConfig() *Config {
	once.Do(func() {
		Cfg = &Config{
			APPPort:          os.Getenv("APP_PORT"),
			Urldatabase:      os.Getenv("URLDATABASE"),
			Databasename:     os.Getenv("DATABASENAME"),
			Userdatabase:     os.Getenv("USERDATABASE"),
			Passworddatabase: os.Getenv("PASSWORDDATABASE"),
			AuthenHost:       os.Getenv("AUTHTHEN_HOST"),
		}
	})
	return Cfg
}
