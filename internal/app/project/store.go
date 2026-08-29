package project

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"github.com/yudopr11/subforge/internal/domain"
)

const ProjectFileName = "project.json"

func SaveProject(proj *domain.Project, dir string) error {
	_ = os.MkdirAll(dir, 0755)
	proj.UpdatedAt = time.Now().UTC()
	data, err := json.MarshalIndent(proj, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal project: %w", err)
	}

	targetPath := filepath.Join(dir, ProjectFileName)
	tmpPath := targetPath + ".tmp"

	if err := os.WriteFile(tmpPath, data, 0644); err != nil {
		return fmt.Errorf("failed to write tmp project file: %w", err)
	}

	if err := os.Rename(tmpPath, targetPath); err != nil {
		return fmt.Errorf("failed to commit project file: %w", err)
	}
	return nil
}

func LoadProject(dir string) (*domain.Project, error) {
	targetPath := filepath.Join(dir, ProjectFileName)
	data, err := os.ReadFile(targetPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read project file: %w", err)
	}

	var proj domain.Project
	if err := json.Unmarshal(data, &proj); err != nil {
		return nil, fmt.Errorf("failed to unmarshal project file: %w", err)
	}
	return &proj, nil
}

func ListProjects(rootDir string) ([]*domain.Project, error) {
	entries, err := os.ReadDir(rootDir)
	if err != nil {
		return nil, err
	}

	var projects []*domain.Project
	// Check current directory
	if proj, err := LoadProject(rootDir); err == nil {
		projects = append(projects, proj)
	}

	// Check subdirectories
	for _, entry := range entries {
		if entry.IsDir() {
			subDir := filepath.Join(rootDir, entry.Name())
			if proj, err := LoadProject(subDir); err == nil {
				projects = append(projects, proj)
			}
		}
	}
	return projects, nil
}
