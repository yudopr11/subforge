package pipeline_test

import (
	"os"
	"path/filepath"
	"runtime"
	"testing"

	"github.com/yudopr11/subforge/internal/app/pipeline"
	"github.com/yudopr11/subforge/internal/domain"
)

func TestParseWhisperJSON(t *testing.T) {
	rawJSON := `{
		"transcription": [
			{"timestamps": {"from": "00:00:01,000", "to": "00:00:03,500"}, "text": " Hello world"},
			{"timestamps": {"from": "00:00:04,000", "to": "00:00:06,200"}, "text": " SubForge Go rewrite"}
		]
	}`

	segments, err := domain.ParseWhisperJSON([]byte(rawJSON))
	if err != nil {
		t.Fatalf("ParseWhisperJSON failed: %v", err)
	}

	if len(segments) != 2 {
		t.Fatalf("Expected 2 segments, got %d", len(segments))
	}
	if segments[0].Source != "Hello world" {
		t.Errorf("Segment[0].Source = %q; want 'Hello world'", segments[0].Source)
	}
	if segments[0].Start != 1.0 || segments[0].End != 3.5 {
		t.Errorf("Segment[0] timing mismatch: %f -> %f", segments[0].Start, segments[0].End)
	}
}

func TestPrepare16kHzAudio_ExistingFile(t *testing.T) {
	tempDir := t.TempDir()
	outWav := filepath.Join(tempDir, "audio.wav")

	// Create dummy wav with size > 44 bytes
	dummyData := make([]byte, 100)
	if err := os.WriteFile(outWav, dummyData, 0644); err != nil {
		t.Fatalf("failed to write dummy wav: %v", err)
	}

	// Calling Prepare16kHzAudio on existing file should skip ffmpeg call and succeed
	err := pipeline.Prepare16kHzAudio("nonexistent.mp3", outWav)
	if err != nil {
		t.Errorf("Prepare16kHzAudio should skip when outWav exists and is >44 bytes, got: %v", err)
	}
}

func TestRunTranscription_MockWhisper(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("skipping shell script test on Windows")
	}

	tempDir := t.TempDir()
	projDir := filepath.Join(tempDir, "project")
	_ = os.MkdirAll(projDir, 0755)

	// Pre-create audio.wav so ffmpeg is skipped
	wavPath := filepath.Join(projDir, "audio.wav")
	_ = os.WriteFile(wavPath, make([]byte, 100), 0644)

	// Create a mock whisper script that creates whisper_out.json
	mockWhisperScript := filepath.Join(tempDir, "mock_whisper.sh")
	scriptContent := `#!/bin/sh
echo "whisper progress: 50%" >&2
echo "whisper progress: 100%" >&2
cat << 'EOF' > "$PWD/whisper_out.json"
{
  "transcription": [
    {"timestamps": {"from": "00:00:00,000", "to": "00:00:02,000"}, "text": " Mocked transcription line"}
  ]
}
EOF
exit 0
`
	if err := os.WriteFile(mockWhisperScript, []byte(scriptContent), 0755); err != nil {
		t.Fatalf("failed to write mock script: %v", err)
	}

	proj := domain.NewProject("test_proj", "dummy.mp3", "small", "en")
	var logs []string
	logFn := func(msg string) {
		logs = append(logs, msg)
	}

	// Change working directory or pass project dir
	origDir, _ := os.Getwd()
	_ = os.Chdir(projDir)
	defer os.Chdir(origDir)

	err := pipeline.RunTranscription(proj, projDir, "mock_model.bin", mockWhisperScript, logFn)
	if err != nil {
		t.Fatalf("RunTranscription failed: %v", err)
	}

	if proj.Stages["transcribe"] != domain.StatusCompleted {
		t.Errorf("Stage status = %v; want 'completed'", proj.Stages["transcribe"])
	}
	if len(proj.Segments) != 1 {
		t.Fatalf("Expected 1 segment, got %d", len(proj.Segments))
	}
	if proj.Segments[0].Source != "Mocked transcription line" {
		t.Errorf("Segment source = %q; want 'Mocked transcription line'", proj.Segments[0].Source)
	}
}
