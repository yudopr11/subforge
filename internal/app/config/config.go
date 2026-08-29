package config

import (
	"encoding/json"
	"os"
	"path/filepath"
)

type AppConfig struct {
	DefaultModel    string `json:"default_model"`
	DefaultLanguage string `json:"default_language"`
	WizardCompleted bool   `json:"wizard_completed"`
	AudioPlayer     string `json:"audio_player,omitempty"`
}

func DefaultConfig() *AppConfig {
	return &AppConfig{
		DefaultModel:    "small",
		DefaultLanguage: "auto",
		WizardCompleted: false,
	}
}

func GetConfigDir() (string, error) {
	cfgDir, err := os.UserConfigDir()
	if err != nil {
		return "", err
	}
	subDir := filepath.Join(cfgDir, "subforge")
	if err := os.MkdirAll(subDir, 0700); err != nil {
		return "", err
	}
	return subDir, nil
}

func LoadConfig() (*AppConfig, error) {
	dir, err := GetConfigDir()
	if err != nil {
		return DefaultConfig(), nil
	}
	return LoadConfigFromPath(filepath.Join(dir, "config.json"))
}

func LoadConfigFromPath(path string) (*AppConfig, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return DefaultConfig(), nil
		}
		return nil, err
	}
	cfg := DefaultConfig()
	if err := json.Unmarshal(data, cfg); err != nil {
		return DefaultConfig(), nil
	}
	return cfg, nil
}

func SaveConfig(cfg *AppConfig) error {
	dir, err := GetConfigDir()
	if err != nil {
		return err
	}
	return SaveConfigToPath(cfg, filepath.Join(dir, "config.json"))
}

func SaveConfigToPath(cfg *AppConfig, targetPath string) error {
	data, err := json.MarshalIndent(cfg, "", "  ")
	if err != nil {
		return err
	}
	tmpPath := targetPath + ".tmp"
	if err := os.WriteFile(tmpPath, data, 0600); err != nil {
		return err
	}
	return os.Rename(tmpPath, targetPath)
}
