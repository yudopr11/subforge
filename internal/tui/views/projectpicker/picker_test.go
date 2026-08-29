package projectpicker_test

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/yudopr11/subforge/internal/app/project"
	"github.com/yudopr11/subforge/internal/domain"
	"github.com/yudopr11/subforge/internal/tui/views/projectpicker"
)

func TestProjectPickerInit(t *testing.T) {
	tempDir := t.TempDir()
	p := domain.NewProject("test_project", "audio.mp3", "small", "en")
	p.Segments = []domain.Segment{{ID: 1, Start: 0, End: 1, Source: "Test"}}
	_ = project.SaveProject(p, tempDir)

	subDir := filepath.Join(tempDir, "sub_proj")
	_ = os.MkdirAll(subDir, 0755)
	p2 := domain.NewProject("sub_project", "audio2.mp3", "small", "en")
	_ = project.SaveProject(p2, subDir)

	m := projectpicker.New(tempDir, 80, 24)
	items := m.List.Items()
	if len(items) != 2 {
		t.Fatalf("Expected 2 project items, got %d", len(items))
	}

	foundTest := false
	for _, it := range items {
		if pi, ok := it.(projectpicker.ProjectItem); ok {
			if pi.Project.Name == "test_project" {
				foundTest = true
			}
		}
	}
	if !foundTest {
		t.Errorf("Project 'test_project' not found in picker list")
	}
}
