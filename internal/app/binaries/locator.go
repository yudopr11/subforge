package binaries

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
)

func GetAppDataDir() (string, error) {
	dataDir, err := os.UserHomeDir()
	if err != nil {
		return "", err
	}
	var dir string
	if runtime.GOOS == "windows" {
		localApp := os.Getenv("LOCALAPPDATA")
		if localApp != "" {
			dir = filepath.Join(localApp, "subforge")
		} else {
			dir = filepath.Join(dataDir, "AppData", "Local", "subforge")
		}
	} else {
		dir = filepath.Join(dataDir, ".local", "share", "subforge")
	}
	if err := os.MkdirAll(dir, 0755); err != nil {
		return "", err
	}
	return dir, nil
}

func FindBinary(name string) (string, error) {
	// 1. Check local subforge bin dir
	dataDir, err := GetAppDataDir()
	if err == nil {
		localBin := filepath.Join(dataDir, "bin", name)
		if runtime.GOOS == "windows" && filepath.Ext(localBin) == "" {
			localBin += ".exe"
		}
		if fi, err := os.Stat(localBin); err == nil && !fi.IsDir() {
			return localBin, nil
		}
	}

	// 2. Check system PATH
	path, err := exec.LookPath(name)
	if err == nil {
		return path, nil
	}

	// 3. Fallback name variants (e.g. whisper-cli / whisper.cpp)
	if name == "whisper-cli" {
		if path, err := exec.LookPath("whisper"); err == nil {
			return path, nil
		}
		if path, err := exec.LookPath("main"); err == nil {
			return path, nil
		}
	}

	return "", fmt.Errorf("binary %q not found in PATH or subforge local bin", name)
}
