package pipeline

import (
	"bufio"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"

	"github.com/yudopr11/subforge/internal/app/binaries"
	"github.com/yudopr11/subforge/internal/domain"
	"github.com/yudopr11/subforge/internal/tui/components"
)

func parseProgressPct(line string) (float64, bool) {
	idx := strings.Index(line, "%")
	if idx == -1 {
		return 0, false
	}
	start := idx - 1
	for start >= 0 && (line[start] >= '0' && line[start] <= '9' || line[start] == '.' || line[start] == ' ') {
		start--
	}
	numStr := strings.TrimSpace(line[start+1 : idx])
	if val, err := strconv.ParseFloat(numStr, 64); err == nil && val >= 0 && val <= 100 {
		return val, true
	}
	return 0, false
}

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
	if err := Prepare16kHzAudio(proj.AudioPath, wavPath, nil); err != nil {
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
		"--print-progress",
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
	cmd.Dir = projectDir
	cmd.Env = binaries.AppendLibraryPath(os.Environ(), filepath.Dir(whisperBin))

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

	var stderrLines []string
	scanner := bufio.NewScanner(stderrPipe)
	for scanner.Scan() {
		line := scanner.Text()
		stderrLines = append(stderrLines, line)
		if pct, ok := parseProgressPct(line); ok {
			if logFn != nil {
				bar := components.FormatPercentBar("▸ Transcribing", pct, 25)
				logFn(bar)
			}
		} else if strings.Contains(line, "%") || strings.Contains(line, "progress") {
			if logFn != nil {
				logFn(line)
			}
		}
	}

	if err := cmd.Wait(); err != nil {
		proj.Stages["transcribe"] = domain.StatusFailed
		detail := ""
		if len(stderrLines) > 0 {
			detail = ": " + strings.Join(stderrLines[max(0, len(stderrLines)-3):], " | ")
		}
		proj.Error = fmt.Sprintf("whisper-cli failed (%v)%s", err, detail)
		return fmt.Errorf("%s", proj.Error)
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
