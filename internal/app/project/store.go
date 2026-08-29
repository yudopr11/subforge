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

func GetProjectDir(baseDir string) string {
	base := filepath.Base(baseDir)
	if base == "subforge" || base == ".subforge" {
		return baseDir
	}
	return filepath.Join(baseDir, "subforge")
}

func SaveProject(proj *domain.Project, dir string) error {
	targetDir := GetProjectDir(dir)
	_ = os.MkdirAll(targetDir, 0755)

	proj.UpdatedAt = time.Now().UTC()
	data, err := json.MarshalIndent(proj, "", "  ")
	if err != nil {
		return fmt.Errorf("failed to marshal project: %w", err)
	}

	targetPath := filepath.Join(targetDir, ProjectFileName)
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
	candidates := []string{
		filepath.Join(dir, "subforge", ProjectFileName),
		filepath.Join(dir, ".subforge", ProjectFileName),
		filepath.Join(dir, ProjectFileName),
	}

	for _, targetPath := range candidates {
		data, err := os.ReadFile(targetPath)
		if err == nil {
			var proj domain.Project
			if jsonErr := json.Unmarshal(data, &proj); jsonErr == nil {
				return &proj, nil
			}
		}
	}

	return nil, fmt.Errorf("no valid project.json found in %s or %s/subforge", dir, dir)
}

func ListProjects(rootDir string) ([]*domain.Project, error) {
	var projects []*domain.Project
	seen := make(map[string]bool)

	// 1. Check root directory / root subforge directory
	if proj, err := LoadProject(rootDir); err == nil {
		projects = append(projects, proj)
		seen[proj.Name] = true
	}

	// 2. Check child subdirectories
	entries, err := os.ReadDir(rootDir)
	if err == nil {
		for _, entry := range entries {
			if entry.IsDir() && entry.Name() != "subforge" && entry.Name() != ".subforge" && entry.Name() != ".git" && entry.Name() != "bin" {
				subDir := filepath.Join(rootDir, entry.Name())
				if proj, err := LoadProject(subDir); err == nil {
					if !seen[proj.Name] {
						projects = append(projects, proj)
						seen[proj.Name] = true
					}
				}
			}
		}
	}

	return projects, nil
}
