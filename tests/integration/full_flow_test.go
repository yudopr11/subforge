package integration_test

import (
	"path/filepath"
	"testing"

	"github.com/yudopr11/subforge/internal/app/export"
	"github.com/yudopr11/subforge/internal/app/project"
	"github.com/yudopr11/subforge/internal/domain"
)

func TestFullProjectCreationAndExportFlow(t *testing.T) {
	tempDir := t.TempDir()

	// 1. Create project
	proj := domain.NewProject("demo_video", filepath.Join(tempDir, "audio.mp3"), "small", "id")
	proj.Segments = []domain.Segment{
		{ID: 1, Start: 0.5, End: 2.5, Source: "Halo selamat datang", Speaker: "Host"},
		{ID: 2, Start: 2.6, End: 5.0, Source: "Di SubForge Go", Speaker: ""},
	}

	// 2. Save project state
	if err := project.SaveProject(proj, tempDir); err != nil {
		t.Fatalf("SaveProject failed: %v", err)
	}

	// 3. Export SRT and ASS
	files, err := export.ExportFiles(proj, tempDir, []string{"srt", "ass"})
	if err != nil {
		t.Fatalf("ExportFiles failed: %v", err)
	}
	if len(files) != 2 {
		t.Fatalf("Expected 2 exported files, got %d", len(files))
	}

	// 4. Verify reload from disk
	loaded, err := project.LoadProject(tempDir)
	if err != nil {
		t.Fatalf("LoadProject failed: %v", err)
	}
	if loaded.Name != "demo_video" || len(loaded.Segments) != 2 {
		t.Fatalf("Loaded project data mismatch: %+v", loaded)
	}
}
