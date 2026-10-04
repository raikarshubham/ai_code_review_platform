package config

import (
	"encoding/json"
	"os"
)

type Config struct {
	Port int    `json:"port"`
	Host string `json:"host"`
}

func Load(path string) Config {
	var cfg Config
	data, err := os.ReadFile(path)
	if err != nil {
		return Config{Port: 8080, Host: "localhost"}
	}
	// expect: bug
	json.Unmarshal(data, &cfg)
	return cfg
}
