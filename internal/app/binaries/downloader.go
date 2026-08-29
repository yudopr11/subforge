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
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
)

func GetWhisperReleaseURL() (string, string) {
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

func GetFFmpegReleaseURL() string {
	switch runtime.GOOS {
	case "windows":
		return "https://github.com/eugeneware/ffmpeg-static/releases/latest/download/ffmpeg-win32-x64"
	case "darwin":
		if runtime.GOARCH == "arm64" {
			return "https://github.com/eugeneware/ffmpeg-static/releases/latest/download/ffmpeg-darwin-arm64"
		}
		return "https://github.com/eugeneware/ffmpeg-static/releases/latest/download/ffmpeg-darwin-x64"
	default: // linux
		if runtime.GOARCH == "arm64" {
			return "https://github.com/eugeneware/ffmpeg-static/releases/latest/download/ffmpeg-linux-arm64"
		}
		return "https://github.com/eugeneware/ffmpeg-static/releases/latest/download/ffmpeg-linux-x64"
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
	return nil
}

func ExtractTarGz(data []byte, destDir string) error {
	gzr, err := gzip.NewReader(bytes.NewReader(data))
	if err != nil {
		return err
	}
	defer gzr.Close()

	tr := tar.NewReader(gzr)
	type symlinkInfo struct {
		target string
		link   string
	}
	var symlinks []symlinkInfo

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

		targetPath := filepath.Join(destDir, name)

		if header.Typeflag == tar.TypeSymlink || header.Typeflag == tar.TypeLink {
			symlinks = append(symlinks, symlinkInfo{
				target: targetPath,
				link:   filepath.Base(header.Linkname),
			})
			continue
		}

		if header.Typeflag == tar.TypeReg || header.Typeflag == tar.TypeRegA || header.Typeflag == 0 {
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

	// Create symlinks/copies after all regular files are extracted
	for _, sl := range symlinks {
		_ = os.Remove(sl.target)
		_ = os.Symlink(sl.link, sl.target)
		// Fallback to file copy if symlink failed
		if _, err := os.Stat(sl.target); err != nil {
			src := filepath.Join(destDir, sl.link)
			if data, err := os.ReadFile(src); err == nil {
				_ = os.WriteFile(sl.target, data, 0755)
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
				progressFn(downloaded, total, "whisper-cli")
			}
		}
		if readErr != nil {
			if readErr == io.EOF {
				break
			}
			return "", readErr
		}
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

func EnsureFFmpegBinary(progressFn func(current, total int64, msg string)) (string, error) {
	if bin, err := FindBinary("ffmpeg"); err == nil {
		testCmd := exec.Command(bin, "-version")
		if err := testCmd.Run(); err == nil {
			return bin, nil
		}
	}

	appDir, err := GetAppDataDir()
	if err != nil {
		return "", err
	}
	binDir := filepath.Join(appDir, "bin")
	_ = os.MkdirAll(binDir, 0755)

	targetBin := filepath.Join(binDir, "ffmpeg")
	if runtime.GOOS == "windows" {
		targetBin += ".exe"
	}

	url := GetFFmpegReleaseURL()
	resp, err := http.Get(url)
	if err != nil {
		return "", fmt.Errorf("failed to download ffmpeg binary: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return "", fmt.Errorf("download ffmpeg failed with HTTP %s", resp.Status)
	}

	total := resp.ContentLength
	tmpPath := targetBin + ".download"
	out, err := os.OpenFile(tmpPath, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0755)
	if err != nil {
		return "", err
	}

	buf := make([]byte, 32*1024)
	var downloaded int64
	for {
		n, readErr := resp.Body.Read(buf)
		if n > 0 {
			if _, writeErr := out.Write(buf[:n]); writeErr != nil {
				out.Close()
				_ = os.Remove(tmpPath)
				return "", writeErr
			}
			downloaded += int64(n)
			if progressFn != nil {
				progressFn(downloaded, total, "ffmpeg")
			}
		}
		if readErr != nil {
			if readErr == io.EOF {
				break
			}
			out.Close()
			_ = os.Remove(tmpPath)
			return "", readErr
		}
	}
	out.Close()

	_ = os.Remove(targetBin)
	if err := os.Rename(tmpPath, targetBin); err != nil {
		return "", err
	}
	_ = os.Chmod(targetBin, 0755)
	return targetBin, nil
}

func AppendLibraryPath(env []string, binDir string) []string {
	sep := string(os.PathListSeparator)
	var newEnv []string
	var existingPath string
	var existingLD string
	var existingDYLD string

	for _, kv := range env {
		parts := strings.SplitN(kv, "=", 2)
		if len(parts) != 2 {
			newEnv = append(newEnv, kv)
			continue
		}
		key := parts[0]
		val := parts[1]

		if strings.EqualFold(key, "PATH") {
			if existingPath == "" {
				existingPath = val
			}
			continue
		}
		if strings.EqualFold(key, "LD_LIBRARY_PATH") {
			if existingLD == "" {
				existingLD = val
			}
			continue
		}
		if strings.EqualFold(key, "DYLD_LIBRARY_PATH") {
			if existingDYLD == "" {
				existingDYLD = val
			}
			continue
		}
		newEnv = append(newEnv, kv)
	}

	newPath := binDir
	if existingPath != "" {
		newPath = binDir + sep + existingPath
	}

	newLd := binDir
	if existingLD != "" {
		newLd = binDir + ":" + existingLD
	}

	newDyld := binDir
	if existingDYLD != "" {
		newDyld = binDir + ":" + existingDYLD
	}

	newEnv = append(newEnv,
		"PATH="+newPath,
		"LD_LIBRARY_PATH="+newLd,
		"DYLD_LIBRARY_PATH="+newDyld,
	)

	return newEnv
}

func EnsureWhisperBinary(progressFn func(current, total int64, msg string)) (string, error) {
	if bin, err := FindBinary("whisper-cli"); err == nil {
		binDir := filepath.Dir(bin)
		testCmd := exec.Command(bin, "--help")
		testCmd.Env = AppendLibraryPath(os.Environ(), binDir)
		if err := testCmd.Run(); err == nil {
			return bin, nil
		}
	}
	return DownloadAndExtractWhisper(progressFn)
}
