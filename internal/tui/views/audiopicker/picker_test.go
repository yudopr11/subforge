package audiopicker_test

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/yudopr11/subforge/internal/tui/views/audiopicker"
)

func TestAudioPickerScanAndInit(t *testing.T) {
	tempDir := t.TempDir()

	// Create sample audio and non-audio files
	_ = os.WriteFile(filepath.Join(tempDir, "sample.mp3"), []byte("dummy"), 0644)
	_ = os.WriteFile(filepath.Join(tempDir, "sample.wav"), []byte("dummy"), 0644)
	_ = os.WriteFile(filepath.Join(tempDir, "notes.txt"), []byte("dummy"), 0644)

	items := audiopicker.ScanAudioFiles(tempDir)
	if len(items) != 2 {
		t.Fatalf("Expected 2 audio items, got %d", len(items))
	}

	m := audiopicker.New(tempDir, 80, 24)
	if len(m.List.Items()) != 2 {
		t.Fatalf("Expected picker list to contain 2 items, got %d", len(m.List.Items()))
	}

	first, ok := m.List.Items()[0].(audiopicker.AudioFileItem)
	if !ok {
		t.Fatalf("Expected item to be AudioFileItem, got %T", m.List.Items()[0])
	}
	if first.Name == "" || first.Path == "" {
		t.Errorf("Empty name or path in AudioFileItem: %+v", first)
	}
	if !strings.Contains(first.FilterValue(), first.Name) {
		t.Errorf("FilterValue() = %q missing Name %q", first.FilterValue(), first.Name)
	}
}
