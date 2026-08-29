package binaries

import (
	"archive/tar"
	"archive/zip"
	"bytes"
	"compress/gzip"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
	"strings"
)

func GetWhisperReleaseURL() (string, string) {
	// Returns (URL, archiveType "zip" or "tar.gz")
	switch runtime.GOOS {
	case "windows":
		return "https://github.com/ggml-org/whisper.cpp/releases/latest/download/whisper-bin-x64.zip", "zip"
	case "darwin":
		if runtime.GOARCH == "arm64" {
			return "https://github.com/ggml-org/whisper.cpp/releases/latest/download/whisper-bin-macos-arm64.tar.gz", "tar.gz"
		}
		return "https://github.com/ggml-org/whisper.cpp/releases/latest/download/whisper-bin-macos-x64.tar.gz", "tar.gz"
	default: // linux
		if runtime.GOARCH == "arm64" {
			return "https://github.com/ggml-org/whisper.cpp/releases/latest/download/whisper-bin-ubuntu-arm64.tar.gz", "tar.gz"
		}
		return "https://github.com/ggml-org/whisper.cpp/releases/latest/download/whisper-bin-ubuntu-x64.tar.gz", "tar.gz"
	}
}

func ExtractZip(data []byte, destDir string) error {
	r, err := zip.NewReader(bytes.NewReader(data), int64(len(data)))
	if err != nil {
		return err
	}

	for _, f := range r.File {
		name := filepath.Base(f.Name)
		if name == "" || f.FileInfo().IsDir() {
			continue
		}
		// Match whisper-cli, main, or dlls/libs
		if strings.HasPrefix(name, "whisper") || strings.HasPrefix(name, "main") || strings.HasSuffix(name, ".dll") {
			targetPath := filepath.Join(destDir, name)
			rc, err := f.Open()
			if err != nil {
				return err
			}
			out, err := os.OpenFile(targetPath, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0755)
			if err != nil {
				rc.Close()
				return err
			}
			_, err = io.Copy(out, rc)
			rc.Close()
			out.Close()
			if err != nil {
				return err
			}
		}
	}
	return nil
}

func ExtractTarGz(data []byte, destDir string) error {
	gzr, err := gzip.NewReader(bytes.NewReader(data))
	if err != nil {
		return err
	}
	defer gzr.Close()

	tr := tar.NewReader(gzr)
	for {
		header, err := tr.Next()
		if err == io.EOF {
			break
		}
		if err != nil {
			return err
		}

		name := filepath.Base(header.Name)
		if name == "" || header.Typeflag == tar.TypeDir {
			continue
		}

		if strings.HasPrefix(name, "whisper") || strings.HasPrefix(name, "main") || strings.HasSuffix(name, ".so") || strings.HasSuffix(name, ".dylib") {
			targetPath := filepath.Join(destDir, name)
			out, err := os.OpenFile(targetPath, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0755)
			if err != nil {
				return err
			}
			_, err = io.Copy(out, tr)
			out.Close()
			if err != nil {
				return err
			}
		}
	}
	return nil
}

func DownloadAndExtractWhisper(progressFn func(current, total int64, msg string)) (string, error) {
	appDir, err := GetAppDataDir()
	if err != nil {
		return "", err
	}
	binDir := filepath.Join(appDir, "bin")
	if err := os.MkdirAll(binDir, 0755); err != nil {
		return "", err
	}

	url, archiveType := GetWhisperReleaseURL()
	resp, err := http.Get(url)
	if err != nil {
		return "", fmt.Errorf("failed to download whisper binary: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("download failed with HTTP %s", resp.Status)
	}

	total := resp.ContentLength
	var downloaded int64
	var buf bytes.Buffer
	chunk := make([]byte, 32*1024)

	for {
		n, readErr := resp.Body.Read(chunk)
		if n > 0 {
			buf.Write(chunk[:n])
			downloaded += int64(n)
			if progressFn != nil {
				progressFn(downloaded, total, fmt.Sprintf("Downloading whisper-cli (%.1f/%.1f MB)", float64(downloaded)/1e6, float64(total)/1e6))
			}
		}
		if readErr != nil {
			if readErr == io.EOF {
				break
			}
			return "", readErr
		}
	}

	if progressFn != nil {
		progressFn(downloaded, total, "Extracting whisper-cli binary...")
	}

	if archiveType == "zip" {
		if err := ExtractZip(buf.Bytes(), binDir); err != nil {
			return "", fmt.Errorf("failed to extract zip: %w", err)
		}
	} else {
		if err := ExtractTarGz(buf.Bytes(), binDir); err != nil {
			return "", fmt.Errorf("failed to extract tar.gz: %w", err)
		}
	}

	// Create alias/symlink for whisper-cli if executable is named 'main'
	targetBin := filepath.Join(binDir, "whisper-cli")
	if runtime.GOOS == "windows" {
		targetBin += ".exe"
	}

	if _, err := os.Stat(targetBin); os.IsNotExist(err) {
		mainBin := filepath.Join(binDir, "main")
		if runtime.GOOS == "windows" {
			mainBin += ".exe"
		}
		if _, err := os.Stat(mainBin); err == nil {
			data, err := os.ReadFile(mainBin)
			if err == nil {
				_ = os.WriteFile(targetBin, data, 0755)
			}
		}
	}

	return targetBin, nil
}

func EnsureWhisperBinary(progressFn func(current, total int64, msg string)) (string, error) {
	if bin, err := FindBinary("whisper-cli"); err == nil {
		return bin, nil
	}
	return DownloadAndExtractWhisper(progressFn)
}
