package project_test

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/yudopr11/subforge/internal/app/project"
	"github.com/yudopr11/subforge/internal/domain"
)

func TestAtomicSaveAndLoadProject(t *testing.T) {
	tempDir := t.TempDir()
	proj := domain.NewProject("episode_01", filepath.Join(tempDir, "audio.mp3"), "small", "en")
	proj.Segments = append(proj.Segments, domain.Segment{
		ID: 1, Start: 0.0, End: 2.0, Source: "Testing store", Speaker: "Bob",
	})

	if err := project.SaveProject(proj, tempDir); err != nil {
		t.Fatalf("SaveProject failed: %v", err)
	}

	loaded, err := project.LoadProject(tempDir)
	if err != nil {
		t.Fatalf("LoadProject failed: %v", err)
	}

	if loaded.Name != proj.Name {
		t.Errorf("Project name mismatch: got %q, want %q", loaded.Name, proj.Name)
	}
	if len(loaded.Segments) != 1 || loaded.Segments[0].Speaker != "Bob" {
		t.Errorf("Segments mismatch: %+v", loaded.Segments)
	}
}

func TestListProjects(t *testing.T) {
	rootDir := t.TempDir()

	// Project in root
	projRoot := domain.NewProject("root_proj", filepath.Join(rootDir, "a.mp3"), "small", "en")
	if err := project.SaveProject(projRoot, rootDir); err != nil {
		t.Fatalf("SaveProject root failed: %v", err)
	}

	// Project in subfolder
	subDir := filepath.Join(rootDir, "sub_proj")
	if err := os.MkdirAll(subDir, 0755); err != nil {
		t.Fatalf("MkdirAll failed: %v", err)
	}
	projSub := domain.NewProject("sub_proj", filepath.Join(subDir, "b.mp3"), "base", "id")
	if err := project.SaveProject(projSub, subDir); err != nil {
		t.Fatalf("SaveProject sub failed: %v", err)
	}

	projects, err := project.ListProjects(rootDir)
	if err != nil {
		t.Fatalf("ListProjects failed: %v", err)
	}

	if len(projects) != 2 {
		t.Errorf("Expected 2 projects, got %d", len(projects))
	}
}
