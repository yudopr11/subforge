package pipeline

import (
	"bufio"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/yudopr11/subforge/internal/domain"
)

func RunTranscription(
	proj *domain.Project,
	projectDir string,
	modelPath string,
	whisperBin string,
	logFn func(string),
) error {
	if proj.Stages == nil {
		proj.Stages = make(map[string]domain.StageStatus)
	}
	proj.Stages["transcribe"] = domain.StatusRunning

	// 1. Prepare 16kHz mono WAV
	wavPath := filepath.Join(projectDir, "audio.wav")
	if logFn != nil {
		logFn("Converting audio to 16kHz mono WAV...")
	}
	if err := Prepare16kHzAudio(proj.AudioPath, wavPath); err != nil {
		proj.Stages["transcribe"] = domain.StatusFailed
		proj.Error = err.Error()
		return err
	}

	// 2. Build whisper-cli command
	jsonOutputBase := filepath.Join(projectDir, "whisper_out")
	args := []string{
		"-m", modelPath,
		"-f", wavPath,
		"--output-json",
		"--output-file", jsonOutputBase,
		"--print-colors", "0",
	}

	if proj.Language != "" && proj.Language != "auto" {
		args = append(args, "-l", proj.Language)
	} else {
		args = append(args, "-l", "auto")
	}

	if logFn != nil {
		logFn(fmt.Sprintf("Running %s with model %s...", filepath.Base(whisperBin), filepath.Base(modelPath)))
	}

	cmd := exec.Command(whisperBin, args...)
	stderrPipe, err := cmd.StderrPipe()
	if err != nil {
		proj.Stages["transcribe"] = domain.StatusFailed
		proj.Error = err.Error()
		return err
	}

	if err := cmd.Start(); err != nil {
		proj.Stages["transcribe"] = domain.StatusFailed
		proj.Error = fmt.Sprintf("failed to start whisper-cli: %v", err)
		return fmt.Errorf("failed to start whisper-cli: %w", err)
	}

	scanner := bufio.NewScanner(stderrPipe)
	for scanner.Scan() {
		line := scanner.Text()
		if strings.Contains(line, "%") || strings.Contains(line, "progress") {
			if logFn != nil {
				logFn(line)
			}
		}
	}

	if err := cmd.Wait(); err != nil {
		proj.Stages["transcribe"] = domain.StatusFailed
		proj.Error = fmt.Sprintf("whisper-cli exited with error: %v", err)
		return err
	}

	// 3. Read generated JSON output
	jsonFilePath := jsonOutputBase + ".json"
	jsonData, err := os.ReadFile(jsonFilePath)
	if err != nil {
		proj.Stages["transcribe"] = domain.StatusFailed
		proj.Error = fmt.Sprintf("failed to read whisper json output: %v", err)
		return fmt.Errorf("failed to read whisper json output: %w", err)
	}

	segments, err := domain.ParseWhisperJSON(jsonData)
	if err != nil {
		proj.Stages["transcribe"] = domain.StatusFailed
		proj.Error = fmt.Sprintf("failed to parse transcript JSON: %v", err)
		return fmt.Errorf("failed to parse transcript JSON: %w", err)
	}

	proj.Segments = segments
	proj.Stages["transcribe"] = domain.StatusCompleted
	proj.Error = ""

	if logFn != nil {
		logFn(fmt.Sprintf("✓ Transcribed %d captions successfully", len(segments)))
	}
	return nil
}
