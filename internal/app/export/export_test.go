package export_test

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/yudopr11/subforge/internal/app/export"
	"github.com/yudopr11/subforge/internal/domain"
)

func TestGenerateSRT(t *testing.T) {
	segments := []domain.Segment{
		{ID: 1, Start: 1.0, End: 3.5, Source: "Hello world.", Speaker: "Alice"},
		{ID: 2, Start: 4.0, End: 6.25, Source: "Welcome to SubForge.", Speaker: ""},
	}

	result := export.GenerateSRT(segments)

	expectedSnippet1 := "1\n00:00:01,000 --> 00:00:03,500\n[Alice]: Hello world."
	expectedSnippet2 := "2\n00:00:04,000 --> 00:00:06,250\nWelcome to SubForge."

	if !strings.Contains(result, expectedSnippet1) {
		t.Errorf("SRT missing snippet 1, got:\n%s", result)
	}
	if !strings.Contains(result, expectedSnippet2) {
		t.Errorf("SRT missing snippet 2, got:\n%s", result)
	}
}

func TestGenerateASS(t *testing.T) {
	segments := []domain.Segment{
		{ID: 1, Start: 1.0, End: 3.5, Source: "Hello world.", Speaker: "Alice"},
	}

	result := export.GenerateASS(segments, "MyVideo")

	if !strings.Contains(result, "[Script Info]") {
		t.Errorf("ASS missing [Script Info]")
	}
	if !strings.Contains(result, "Title: MyVideo") {
		t.Errorf("ASS missing Title header")
	}
	if !strings.Contains(result, "Dialogue: 0,0:00:01.00,0:00:03.50,Default,Alice,0,0,0,,Hello world.") {
		t.Errorf("ASS missing Dialogue line, got:\n%s", result)
	}
}

func TestExportFiles(t *testing.T) {
	tempDir := t.TempDir()
	proj := domain.NewProject("test_export", filepath.Join(tempDir, "audio.mp3"), "small", "en")
	proj.Segments = []domain.Segment{
		{ID: 1, Start: 1.0, End: 3.5, Source: "Line 1", Speaker: "Alice"},
		{ID: 2, Start: 4.0, End: 6.0, Source: "Line 2", Speaker: ""},
	}

	files, err := export.ExportFiles(proj, tempDir, []string{"srt", "ass"})
	if err != nil {
		t.Fatalf("ExportFiles failed: %v", err)
	}

	if len(files) != 2 {
		t.Fatalf("Expected 2 exported files, got %d", len(files))
	}

	for _, path := range files {
		data, err := os.ReadFile(path)
		if err != nil {
			t.Errorf("Failed to read exported file %s: %v", path, err)
		}
		if len(data) == 0 {
			t.Errorf("Exported file %s is empty", path)
		}
	}
}
