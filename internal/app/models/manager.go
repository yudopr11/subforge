package models

import (
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"

	"github.com/yudopr11/subforge/internal/app/binaries"
)

type ModelInfo struct {
	Name        string `json:"name"`
	FileName    string `json:"file_name"`
	SizeMB      int    `json:"size_mb"`
	URL         string `json:"url"`
	Description string `json:"description"`
}

var standardModels = []ModelInfo{
	{
		Name:        "tiny",
		FileName:    "ggml-tiny.bin",
		SizeMB:      75,
		URL:         "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin",
		Description: "Fastest, minimal RAM (<1GB), lower accuracy",
	},
	{
		Name:        "base",
		FileName:    "ggml-base.bin",
		SizeMB:      142,
		URL:         "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin",
		Description: "Fast, lightweight (~1GB RAM)",
	},
	{
		Name:        "small",
		FileName:    "ggml-small.bin",
		SizeMB:      466,
		URL:         "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin",
		Description: "Recommended: Great balance of accuracy & speed (~2GB RAM)",
	},
	{
		Name:        "medium",
		FileName:    "ggml-medium.bin",
		SizeMB:      1500,
		URL:         "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin",
		Description: "High accuracy, requires ~5GB RAM",
	},
	{
		Name:        "large-v3",
		FileName:    "ggml-large-v3.bin",
		SizeMB:      3100,
		URL:         "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3.bin",
		Description: "Maximum accuracy, requires ~8GB+ RAM",
	},
}

func GetAvailableModels() []ModelInfo {
	return standardModels
}

type Manager struct {
	modelsDir string
}

func NewManager(customDir string) *Manager {
	if customDir != "" {
		_ = os.MkdirAll(customDir, 0755)
		return &Manager{modelsDir: customDir}
	}
	appDir, _ := binaries.GetAppDataDir()
	dir := filepath.Join(appDir, "models")
	_ = os.MkdirAll(dir, 0755)
	return &Manager{modelsDir: dir}
}

func (m *Manager) GetModelPath(name string) (string, bool) {
	for _, info := range standardModels {
		if info.Name == name {
			target := filepath.Join(m.modelsDir, info.FileName)
			if fi, err := os.Stat(target); err == nil && !fi.IsDir() && fi.Size() > 1024*1024 {
				return target, true
			}
			return target, false
		}
	}
	return "", false
}

func (m *Manager) DeleteModel(name string) error {
	path, exists := m.GetModelPath(name)
	if !exists {
		return fmt.Errorf("model %q is not installed", name)
	}
	return os.Remove(path)
}

func (m *Manager) DownloadModel(name string, progressFn func(current, total int64)) (string, error) {
	var targetInfo *ModelInfo
	for _, info := range standardModels {
		if info.Name == name {
			targetInfo = &info
			break
		}
	}
	if targetInfo == nil {
		return "", fmt.Errorf("unknown model %q", name)
	}

	targetPath := filepath.Join(m.modelsDir, targetInfo.FileName)
	tmpPath := targetPath + ".download"

	resp, err := http.Get(targetInfo.URL)
	if err != nil {
		return "", fmt.Errorf("failed to fetch model: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("bad HTTP status: %s", resp.Status)
	}

	total := resp.ContentLength
	out, err := os.Create(tmpPath)
	if err != nil {
		return "", err
	}
	defer out.Close()

	buf := make([]byte, 32*1024)
	var current int64
	for {
		n, readErr := resp.Body.Read(buf)
		if n > 0 {
			if _, writeErr := out.Write(buf[:n]); writeErr != nil {
				return "", writeErr
			}
			current += int64(n)
			if progressFn != nil {
				progressFn(current, total)
			}
		}
		if readErr != nil {
			if readErr == io.EOF {
				break
			}
			return "", readErr
		}
	}

	out.Close()
	if err := os.Rename(tmpPath, targetPath); err != nil {
		return "", err
	}
	return targetPath, nil
}
