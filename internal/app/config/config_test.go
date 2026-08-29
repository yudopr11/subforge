package config_test

import (
	"path/filepath"
	"testing"

	"github.com/yudopr11/subforge/internal/app/config"
)

func TestRecommendModel(t *testing.T) {
	tests := []struct {
		ram      float64
		expected string
	}{
		{2.0, "tiny"},
		{3.5, "base"},
		{6.0, "small"},
		{12.0, "medium"},
		{32.0, "large-v3"},
	}

	for _, tt := range tests {
		got := config.RecommendModelForRAM(tt.ram)
		if got != tt.expected {
			t.Errorf("RecommendModelForRAM(%f) = %q; want %q", tt.ram, got, tt.expected)
		}
	}
}

func TestDetectHardware(t *testing.T) {
	ram, cpu, rec := config.DetectHardware()
	if ram <= 0 {
		t.Errorf("Expected ram > 0, got %f", ram)
	}
	if cpu <= 0 {
		t.Errorf("Expected cpu > 0, got %d", cpu)
	}
	if rec == "" {
		t.Errorf("Expected non-empty recommended model")
	}
}

func TestAppConfigSaveLoad(t *testing.T) {
	tempDir := t.TempDir()
	configPath := filepath.Join(tempDir, "config.json")

	cfg := &config.AppConfig{
		DefaultModel:    "small",
		DefaultLanguage: "id",
		WizardCompleted: true,
	}

	if err := config.SaveConfigToPath(cfg, configPath); err != nil {
		t.Fatalf("SaveConfigToPath failed: %v", err)
	}

	loaded, err := config.LoadConfigFromPath(configPath)
	if err != nil {
		t.Fatalf("LoadConfigFromPath failed: %v", err)
	}

	if loaded.DefaultModel != "small" || loaded.DefaultLanguage != "id" || !loaded.WizardCompleted {
		t.Errorf("Loaded config mismatch: %+v", loaded)
	}
}
