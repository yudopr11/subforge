package models_test

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/yudopr11/subforge/internal/app/models"
)

func TestAvailableModels(t *testing.T) {
	avail := models.GetAvailableModels()
	if len(avail) < 5 {
		t.Fatalf("Expected at least 5 standard models, got %d", len(avail))
	}
	foundSmall := false
	for _, m := range avail {
		if m.Name == "small" {
			foundSmall = true
			if m.SizeMB == 0 || m.FileName == "" {
				t.Errorf("Invalid small model metadata: %+v", m)
			}
		}
	}
	if !foundSmall {
		t.Errorf("Model 'small' not found in available models list")
	}
}

func TestModelPathResolutionAndDeletion(t *testing.T) {
	tempDir := t.TempDir()
	mgr := models.NewManager(tempDir)

	_, exists := mgr.GetModelPath("small")
	if exists {
		t.Errorf("Expected small model to not exist yet in empty temp dir")
	}

	// Create fake model file > 1MB
	fakeModelPath := filepath.Join(tempDir, "ggml-small.bin")
	dummyData := make([]byte, 1024*1024+10)
	if err := os.WriteFile(fakeModelPath, dummyData, 0644); err != nil {
		t.Fatalf("Failed to create fake model: %v", err)
	}

	path, exists := mgr.GetModelPath("small")
	if !exists || path != fakeModelPath {
		t.Errorf("GetModelPath('small') = (%q, %v); want (%q, true)", path, exists, fakeModelPath)
	}

	// Delete model
	if err := mgr.DeleteModel("small"); err != nil {
		t.Fatalf("DeleteModel failed: %v", err)
	}

	_, existsAfter := mgr.GetModelPath("small")
	if existsAfter {
		t.Errorf("Expected model to be deleted, but still exists")
	}
}
