package binaries_test

import (
	"archive/tar"
	"archive/zip"
	"bytes"
	"compress/gzip"
	"os"
	"path/filepath"
	"testing"

	"github.com/yudopr11/subforge/internal/app/binaries"
)

func TestExtractZip(t *testing.T) {
	tempDir := t.TempDir()

	// Create in-memory zip containing whisper-cli
	var buf bytes.Buffer
	zw := zip.NewWriter(&buf)
	f, err := zw.Create("whisper-cli")
	if err != nil {
		t.Fatalf("Create failed: %v", err)
	}
	_, _ = f.Write([]byte("mock binary content"))
	_ = zw.Close()

	if err := binaries.ExtractZip(buf.Bytes(), tempDir); err != nil {
		t.Fatalf("ExtractZip failed: %v", err)
	}

	target := filepath.Join(tempDir, "whisper-cli")
	if _, err := os.Stat(target); os.IsNotExist(err) {
		t.Errorf("Expected whisper-cli to be extracted to %s", target)
	}
}

func TestExtractTarGz(t *testing.T) {
	tempDir := t.TempDir()

	// Create in-memory tar.gz containing whisper-cli
	var buf bytes.Buffer
	gzw := gzip.NewWriter(&buf)
	tw := tar.NewWriter(gzw)

	content := []byte("mock binary content")
	hdr := &tar.Header{
		Name: "whisper-cli",
		Mode: 0755,
		Size: int64(len(content)),
	}
	if err := tw.WriteHeader(hdr); err != nil {
		t.Fatalf("WriteHeader failed: %v", err)
	}
	_, _ = tw.Write(content)
	_ = tw.Close()
	_ = gzw.Close()

	if err := binaries.ExtractTarGz(buf.Bytes(), tempDir); err != nil {
		t.Fatalf("ExtractTarGz failed: %v", err)
	}

	target := filepath.Join(tempDir, "whisper-cli")
	if _, err := os.Stat(target); os.IsNotExist(err) {
		t.Errorf("Expected whisper-cli to be extracted to %s", target)
	}
}
