package binaries_test

import (
	"testing"

	"github.com/yudopr11/subforge/internal/app/binaries"
)

func TestGetAppDataDir(t *testing.T) {
	dir, err := binaries.GetAppDataDir()
	if err != nil {
		t.Fatalf("GetAppDataDir returned error: %v", err)
	}
	if dir == "" {
		t.Errorf("GetAppDataDir returned empty string")
	}
}

func TestFindBinary_NotFound(t *testing.T) {
	_, err := binaries.FindBinary("non_existent_binary_subforge_12345")
	if err == nil {
		t.Errorf("Expected error for non-existent binary, got nil")
	}
}
