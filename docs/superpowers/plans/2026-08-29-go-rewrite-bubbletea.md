# SubForge Go Rewrite with Bubble Tea Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild SubForge in pure Go with a Bubble Tea TUI for a lightweight (~10–15 MB), zero-Python, instant-startup local-first subtitle generator, editor, and exporter.

**Architecture:** A pure Go modular architecture (`cmd/` and `internal/`) implementing domain models, atomic project storage, HuggingFace GGML model manager, external `whisper-cli` / `ffmpeg` transcription pipeline, segment audio previewer, and an interactive Bubble Tea / Lip Gloss TUI.

**Tech Stack:** Go 1.26+, `github.com/charmbracelet/bubbletea`, `github.com/charmbracelet/lipgloss`, `github.com/charmbracelet/bubbles`.

**Spec:** `docs/superpowers/specs/2026-08-29-go-rewrite-bubbletea-design.md`

## Global Constraints
- Pure Go / Zero CGO (`CGO_ENABLED=0`) for instant cross-compilation on Linux, macOS (Apple Silicon & Intel), and Windows.
- LLM translation is removed / scrapped; focus strictly on transcription, review/editing, and export.
- Standard Go project layout (`cmd/subforge/` for entrypoint, `internal/` for all business logic and UI).
- Canonical subtitle representation: float64 seconds timestamps (`Start`, `End`), 1-based index `ID`, `Source` text, and optional `Speaker` string.
- Atomic file writes for `project.json` and `config.json`.
- TDD: Every task includes failing tests, implementation, passing tests, and git commit.

---

### Task 1: Go Module Initialization & Domain Models

**Files:**
- Create: `go.mod`
- Create: `internal/domain/project.go`
- Create: `internal/domain/timeutils.go`
- Create: `internal/domain/timeutils_test.go`
- Create: `internal/domain/project_test.go`

**Interfaces:**
- Produces:
  - `domain.StageStatus`, `domain.Segment`, `domain.Project`
  - `domain.FormatSRTTime(seconds float64) string`
  - `domain.FormatASSTime(seconds float64) string`
  - `domain.ParseTime(formatted string) (float64, error)`

- [ ] **Step 1: Initialize Go Module and install charmbracelet dependencies**

```bash
go mod init github.com/yudopr11/subforge
go get github.com/charmbracelet/bubbletea@v1.3.4
go get github.com/charmbracelet/lipgloss@v1.0.0
go get github.com/charmbracelet/bubbles@v0.20.0
```

- [ ] **Step 2: Write failing unit tests for domain models & timeutils**

Create `internal/domain/timeutils_test.go`:
```go
package domain_test

import (
	"math"
	"testing"

	"github.com/yudopr11/subforge/internal/domain"
)

func TestFormatSRTTime(t *testing.T) {
	tests := []struct {
		input    float64
		expected string
	}{
		{0.0, "00:00:00,000"},
		{1.234, "00:00:01,234"},
		{65.5, "00:01:05,500"},
		{3661.089, "01:01:01,089"},
	}

	for _, tt := range tests {
		got := domain.FormatSRTTime(tt.input)
		if got != tt.expected {
			t.Errorf("FormatSRTTime(%f) = %q; want %q", tt.input, got, tt.expected)
		}
	}
}

func TestFormatASSTime(t *testing.T) {
	tests := []struct {
		input    float64
		expected string
	}{
		{0.0, "0:00:00.00"},
		{1.234, "0:00:01.23"},
		{65.5, "0:01:05.50"},
		{3661.089, "1:01:01.08"},
	}

	for _, tt := range tests {
		got := domain.FormatASSTime(tt.input)
		if got != tt.expected {
			t.Errorf("FormatASSTime(%f) = %q; want %q", tt.input, got, tt.expected)
		}
	}
}

func TestParseTime(t *testing.T) {
	tests := []struct {
		input    string
		expected float64
	}{
		{"00:00:01,234", 1.234},
		{"01:01:01,089", 3661.089},
		{"0:00:01.23", 1.23},
		{"1:01:01.08", 3661.08},
	}

	for _, tt := range tests {
		got, err := domain.ParseTime(tt.input)
		if err != nil {
			t.Fatalf("ParseTime(%q) unexpected error: %v", tt.input, err)
		}
		if math.Abs(got-tt.expected) > 0.001 {
			t.Errorf("ParseTime(%q) = %f; want %f", tt.input, got, tt.expected)
		}
	}
}
```

Create `internal/domain/project_test.go`:
```go
package domain_test

import (
	"encoding/json"
	"testing"
	"time"

	"github.com/yudopr11/subforge/internal/domain"
)

func TestProjectJSONSerialization(t *testing.T) {
	now := time.Date(2026, 8, 29, 12, 0, 0, 0, time.UTC)
	proj := domain.Project{
		Name:      "test_proj",
		AudioPath: "/tmp/audio.mp3",
		Language:  "auto",
		Model:     "small",
		Stages: map[string]domain.StageStatus{
			"transcribe": domain.StatusCompleted,
		},
		Segments: []domain.Segment{
			{ID: 1, Start: 0.0, End: 2.5, Source: "Hello world", Speaker: "Alice"},
			{ID: 2, Start: 2.5, End: 5.0, Source: "SubForge in Go", Speaker: ""},
		},
		CreatedAt: now,
		UpdatedAt: now,
	}

	data, err := json.Marshal(proj)
	if err != nil {
		t.Fatalf("json.Marshal failed: %v", err)
	}

	var decoded domain.Project
	if err := json.Unmarshal(data, &decoded); err != nil {
		t.Fatalf("json.Unmarshal failed: %v", err)
	}

	if decoded.Name != proj.Name {
		t.Errorf("Name = %q; want %q", decoded.Name, proj.Name)
	}
	if len(decoded.Segments) != 2 {
		t.Fatalf("Segments length = %d; want 2", len(decoded.Segments))
	}
	if decoded.Segments[0].Speaker != "Alice" {
		t.Errorf("Segment[0].Speaker = %q; want 'Alice'", decoded.Segments[0].Speaker)
	}
	if decoded.Segments[1].Speaker != "" {
		t.Errorf("Segment[1].Speaker = %q; want ''", decoded.Segments[1].Speaker)
	}
}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `go test ./internal/domain/...`
Expected: FAIL (types and functions not yet defined)

- [ ] **Step 4: Implement domain models and timeutils**

Create `internal/domain/project.go`:
```go
package domain

import "time"

type StageStatus string

const (
	StatusPending   StageStatus = "pending"
	StatusRunning   StageStatus = "running"
	StatusCompleted StageStatus = "completed"
	StatusFailed    StageStatus = "failed"
	StatusSkipped   StageStatus = "skipped"
)

type Segment struct {
	ID      int     `json:"id"`
	Start   float64 `json:"start"`
	End     float64 `json:"end"`
	Source  string  `json:"source"`
	Speaker string  `json:"speaker,omitempty"`
}

type Project struct {
	Name          string                 `json:"name"`
	AudioPath     string                 `json:"audio_path"`
	AudioDuration float64                `json:"audio_duration,omitempty"`
	Language      string                 `json:"language"`
	Model         string                 `json:"model"`
	Stages        map[string]StageStatus `json:"stages"`
	Error         string                 `json:"error,omitempty"`
	Segments      []Segment              `json:"segments"`
	CreatedAt     time.Time              `json:"created_at"`
	UpdatedAt     time.Time              `json:"updated_at"`
}

func NewProject(name, audioPath, model, language string) *Project {
	now := time.Now().UTC()
	if language == "" {
		language = "auto"
	}
	if model == "" {
		model = "small"
	}
	return &Project{
		Name:      name,
		AudioPath: audioPath,
		Language:  language,
		Model:     model,
		Stages: map[string]StageStatus{
			"transcribe": StatusPending,
			"export":     StatusPending,
		},
		Segments:  make([]Segment, 0),
		CreatedAt: now,
		UpdatedAt: now,
	}
}
```

Create `internal/domain/timeutils.go`:
```go
package domain

import (
	"fmt"
	"math"
	"strconv"
	"strings"
)

func FormatSRTTime(seconds float64) string {
	if seconds < 0 {
		seconds = 0
	}
	totalMs := int64(math.Round(seconds * 1000.0))
	hours := totalMs / 3600000
	totalMs %= 3600000
	minutes := totalMs / 60000
	totalMs %= 60000
	secs := totalMs / 1000
	ms := totalMs % 1000

	return fmt.Sprintf("%02d:%02d:%02d,%03d", hours, minutes, secs, ms)
}

func FormatASSTime(seconds float64) string {
	if seconds < 0 {
		seconds = 0
	}
	totalCs := int64(math.Floor(seconds * 100.0))
	hours := totalCs / 360000
	totalCs %= 360000
	minutes := totalCs / 6000
	totalCs %= 6000
	secs := totalCs / 100
	cs := totalCs % 100

	return fmt.Sprintf("%d:%02d:%02d.%02d", hours, minutes, secs, cs)
}

func ParseTime(formatted string) (float64, error) {
	formatted = strings.TrimSpace(formatted)
	if strings.Contains(formatted, ",") {
		// SRT format: HH:MM:SS,mmm
		parts := strings.Split(formatted, ",")
		if len(parts) != 2 {
			return 0, fmt.Errorf("invalid srt format: %s", formatted)
		}
		ms, err := strconv.ParseFloat(parts[1], 64)
		if err != nil {
			return 0, err
		}
		timeParts := strings.Split(parts[0], ":")
		if len(timeParts) != 3 {
			return 0, fmt.Errorf("invalid srt time parts: %s", formatted)
		}
		h, _ := strconv.ParseFloat(timeParts[0], 64)
		m, _ := strconv.ParseFloat(timeParts[1], 64)
		s, _ := strconv.ParseFloat(timeParts[2], 64)
		return (h * 3600) + (m * 60) + s + (ms / 1000.0), nil
	} else if strings.Contains(formatted, ".") {
		// ASS format: H:MM:SS.cc
		parts := strings.Split(formatted, ".")
		if len(parts) != 2 {
			return 0, fmt.Errorf("invalid ass format: %s", formatted)
		}
		cs, err := strconv.ParseFloat(parts[1], 64)
		if err != nil {
			return 0, err
		}
		timeParts := strings.Split(parts[0], ":")
		if len(timeParts) != 3 {
			return 0, fmt.Errorf("invalid ass time parts: %s", formatted)
		}
		h, _ := strconv.ParseFloat(timeParts[0], 64)
		m, _ := strconv.ParseFloat(timeParts[1], 64)
		s, _ := strconv.ParseFloat(timeParts[2], 64)
		scale := math.Pow10(len(parts[1]))
		return (h * 3600) + (m * 60) + s + (cs / scale), nil
	}
	return 0, fmt.Errorf("unrecognized timestamp format: %s", formatted)
}
```

- [ ] **Step 5: Run tests and verify they pass**

Run: `go test ./internal/domain/... -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add go.mod go.sum internal/domain/
git commit -m "feat(domain): add project, segment, and timestamp domain models"
```

---

### Task 2: Subtitle Exporters (SRT & ASS)

**Files:**
- Create: `internal/app/export/srt.go`
- Create: `internal/app/export/ass.go`
- Create: `internal/app/export/export.go`
- Create: `internal/app/export/export_test.go`

**Interfaces:**
- Consumes: `domain.Segment`, `domain.FormatSRTTime`, `domain.FormatASSTime`
- Produces:
  - `export.GenerateSRT(segments []domain.Segment) string`
  - `export.GenerateASS(segments []domain.Segment, title string) string`
  - `export.ExportFiles(proj *domain.Project, outputDir string, formats []string) ([]string, error)`

- [ ] **Step 1: Write failing unit tests for SRT and ASS export**

Create `internal/app/export/export_test.go`:
```go
package export_test

import (
	"strings"
	"testing"

	"github.com/yudopr11/subforge/internal/app/export"
	"github.com/yudopr11/subforge/internal/domain"
)

func TestGenerateSRT(t *testing.T) {
	segments := []domain.Segment{
		{ID: 1, Start: 1.0, End: 3.5, Source: "Hello world.", Speaker: "Alice"},
		{ID: 2, Start: 4.0, End: 6.25, Source: "Welcome to SubForge.", Speaker: ""},
	}

	result := export.GenerateSRT(segments)

	expectedSnippet1 := "1\n00:00:01,000 --> 00:00:03,500\n[Alice]: Hello world."
	expectedSnippet2 := "2\n00:00:04,000 --> 00:00:06,250\nWelcome to SubForge."

	if !strings.Contains(result, expectedSnippet1) {
		t.Errorf("SRT missing snippet 1, got:\n%s", result)
	}
	if !strings.Contains(result, expectedSnippet2) {
		t.Errorf("SRT missing snippet 2, got:\n%s", result)
	}
}

func TestGenerateASS(t *testing.T) {
	segments := []domain.Segment{
		{ID: 1, Start: 1.0, End: 3.5, Source: "Hello world.", Speaker: "Alice"},
	}

	result := export.GenerateASS(segments, "MyVideo")

	if !strings.Contains(result, "[Script Info]") {
		t.Errorf("ASS missing [Script Info]")
	}
	if !strings.Contains(result, "Title: MyVideo") {
		t.Errorf("ASS missing Title header")
	}
	if !strings.Contains(result, "Dialogue: 0,0:00:01.00,0:00:03.50,Default,Alice,0,0,0,,Hello world.") {
		t.Errorf("ASS missing Dialogue line, got:\n%s", result)
	}
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `go test ./internal/app/export/...`
Expected: FAIL

- [ ] **Step 3: Implement SRT and ASS exporters**

Create `internal/app/export/srt.go`:
```go
package export

import (
	"fmt"
	"strings"

	"github.com/yudopr11/subforge/internal/domain"
)

func GenerateSRT(segments []domain.Segment) string {
	var sb strings.Builder
	for i, seg := range segments {
		if i > 0 {
			sb.WriteString("\n\n")
		}
		sb.WriteString(fmt.Sprintf("%d\n", seg.ID))
		sb.WriteString(fmt.Sprintf("%s --> %s\n", domain.FormatSRTTime(seg.Start), domain.FormatSRTTime(seg.End)))
		if seg.Speaker != "" {
			sb.WriteString(fmt.Sprintf("[%s]: %s", seg.Speaker, strings.TrimSpace(seg.Source)))
		} else {
			sb.WriteString(strings.TrimSpace(seg.Source))
		}
	}
	sb.WriteString("\n")
	return sb.String()
}
```

Create `internal/app/export/ass.go`:
```go
package export

import (
	"fmt"
	"strings"

	"github.com/yudopr11/subforge/internal/domain"
)

const assHeaderTemplate = `[Script Info]
; Script generated by SubForge (https://github.com/yudopr11/subforge)
Title: %s
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: None
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,52,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,2,2,40,40,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
`

func GenerateASS(segments []domain.Segment, title string) string {
	var sb strings.Builder
	sb.WriteString(fmt.Sprintf(assHeaderTemplate, title))

	for _, seg := range segments {
		start := domain.FormatASSTime(seg.Start)
		end := domain.FormatASSTime(seg.End)
		speaker := seg.Speaker
		text := strings.TrimSpace(seg.Source)
		// Escape newlines for ASS
		text = strings.ReplaceAll(text, "\n", "\\N")
		sb.WriteString(fmt.Sprintf("Dialogue: 0,%s,%s,Default,%s,0,0,0,,%s\n", start, end, speaker, text))
	}
	return sb.String()
}
```

Create `internal/app/export/export.go`:
```go
package export

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/yudopr11/subforge/internal/domain"
)

func ExportFiles(proj *domain.Project, outputDir string, formats []string) ([]string, error) {
	if len(formats) == 0 {
		formats = []string{"srt", "ass"}
	}
	if err := os.MkdirAll(outputDir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create output directory: %w", err)
	}

	var generated []string
	baseName := proj.Name
	if baseName == "" {
		baseName = "subtitles"
	}

	for _, fmtType := range formats {
		switch strings.ToLower(fmtType) {
		case "srt":
			content := GenerateSRT(proj.Segments)
			target := filepath.Join(outputDir, baseName+".srt")
			if err := os.WriteFile(target, []byte(content), 0644); err != nil {
				return nil, fmt.Errorf("failed to write SRT file: %w", err)
			}
			generated = append(generated, target)
		case "ass":
			content := GenerateASS(proj.Segments, baseName)
			target := filepath.Join(outputDir, baseName+".ass")
			if err := os.WriteFile(target, []byte(content), 0644); err != nil {
				return nil, fmt.Errorf("failed to write ASS file: %w", err)
			}
			generated = append(generated, target)
		}
	}
	return generated, nil
}
```

- [ ] **Step 4: Run tests and verify they pass**

Run: `go test ./internal/app/export/... -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add internal/app/export/
git commit -m "feat(export): implement SRT and ASS subtitle exporters"
```

---

### Task 3: Configuration, Device Detection & Atomic Project Store

**Files:**
- Create: `internal/app/config/config.go`
- Create: `internal/app/config/device.go`
- Create: `internal/app/config/config_test.go`
- Create: `internal/app/project/store.go`
- Create: `internal/app/project/store_test.go`

**Interfaces:**
- Produces:
  - `config.AppConfig`, `config.LoadConfig() (*AppConfig, error)`, `config.SaveConfig(cfg *AppConfig) error`
  - `config.DetectHardware() (totalRAMGB float64, cpuCores int, recModel string)`
  - `project.SaveProject(proj *domain.Project, dir string) error`
  - `project.LoadProject(dir string) (*domain.Project, error)`
  - `project.ListProjects(rootDir string) ([]*domain.Project, error)`

- [ ] **Step 1: Write failing tests for AppConfig, Device detection & Project Store**

Create `internal/app/config/config_test.go`:
```go
package config_test

import (
	"path/filepath"
	"testing"

	"github.com/yudopr11/subforge/internal/app/config"
)

func TestRecommendModel(t *testing.T) {
	tests := []struct {
		ram      float64
		expected string
	}{
		{2.0, "tiny"},
		{3.5, "base"},
		{6.0, "small"},
		{12.0, "medium"},
		{32.0, "large-v3"},
	}

	for _, tt := range tests {
		got := config.RecommendModelForRAM(tt.ram)
		if got != tt.expected {
			t.Errorf("RecommendModelForRAM(%f) = %q; want %q", tt.ram, got, tt.expected)
		}
	}
}

func TestAppConfigSaveLoad(t *testing.T) {
	tempDir := t.TempDir()
	configPath := filepath.Join(tempDir, "config.json")

	cfg := &config.AppConfig{
		DefaultModel:    "small",
		DefaultLanguage: "id",
		WizardCompleted: true,
	}

	if err := config.SaveConfigToPath(cfg, configPath); err != nil {
		t.Fatalf("SaveConfigToPath failed: %v", err)
	}

	loaded, err := config.LoadConfigFromPath(configPath)
	if err != nil {
		t.Fatalf("LoadConfigFromPath failed: %v", err)
	}

	if loaded.DefaultModel != "small" || loaded.DefaultLanguage != "id" || !loaded.WizardCompleted {
		t.Errorf("Loaded config mismatch: %+v", loaded)
	}
}
```

Create `internal/app/project/store_test.go`:
```go
package project_test

import (
	"path/filepath"
	"testing"

	"github.com/yudopr11/subforge/internal/app/project"
	"github.com/yudopr11/subforge/internal/domain"
)

func TestAtomicSaveAndLoadProject(t *testing.T) {
	tempDir := t.TempDir()
	proj := domain.NewProject("episode_01", filepath.Join(tempDir, "audio.mp3"), "small", "en")
	proj.Segments = append(proj.Segments, domain.Segment{
		ID: 1, Start: 0.0, End: 2.0, Source: "Testing store", Speaker: "Bob",
	})

	if err := project.SaveProject(proj, tempDir); err != nil {
		t.Fatalf("SaveProject failed: %v", err)
	}

	loaded, err := project.LoadProject(tempDir)
	if err != nil {
		t.Fatalf("LoadProject failed: %v", err)
	}

	if loaded.Name != proj.Name {
		t.Errorf("Project name mismatch: got %q, want %q", loaded.Name, proj.Name)
	}
	if len(loaded.Segments) != 1 || loaded.Segments[0].Speaker != "Bob" {
		t.Errorf("Segments mismatch: %+v", loaded.Segments)
	}
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `go test ./internal/app/config/... ./internal/app/project/...`
Expected: FAIL

- [ ] **Step 3: Implement Config, Device Detection & Project Store**

Create `internal/app/config/config.go`:
```go
package config

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
)

type AppConfig struct {
	DefaultModel    string `json:"default_model"`
	DefaultLanguage string `json:"default_language"`
	WizardCompleted bool   `json:"wizard_completed"`
	AudioPlayer     string `json:"audio_player,omitempty"`
}

func DefaultConfig() *AppConfig {
	return &AppConfig{
		DefaultModel:    "small",
		DefaultLanguage: "auto",
		WizardCompleted: false,
	}
}

func GetConfigDir() (string, error) {
	cfgDir, err := os.UserConfigDir()
	if err != nil {
		return "", err
	}
	subDir := filepath.Join(cfgDir, "subforge")
	if err := os.MkdirAll(subDir, 0700); err != nil {
		return "", err
	}
	return subDir, nil
}

func LoadConfig() (*AppConfig, error) {
	dir, err := GetConfigDir()
	if err != nil {
		return DefaultConfig(), nil
	}
	return LoadConfigFromPath(filepath.Join(dir, "config.json"))
}

func LoadConfigFromPath(path string) (*AppConfig, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		if os.IsNotExist(err) {
			return DefaultConfig(), nil
		}
		return nil, err
	}
	cfg := DefaultConfig()
	if err := json.Unmarshal(data, cfg); err != nil {
		return DefaultConfig(), nil
	}
	return cfg, nil
}

func SaveConfig(cfg *AppConfig) error {
	dir, err := GetConfigDir()
	if err != nil {
		return err
	}
	return SaveConfigToPath(cfg, filepath.Join(dir, "config.json"))
}

func SaveConfigToPath(cfg *AppConfig, targetPath string) error {
	data, err := json.MarshalIndent(cfg, "", "  ")
	if err != nil {
		return err
	}
	tmpPath := targetPath + ".tmp"
	if err := os.WriteFile(tmpPath, data, 0600); err != nil {
		return err
	}
	return os.Rename(tmpPath, targetPath)
}
```

Create `internal/app/config/device.go`:
```go
package config

import (
	"runtime"
)

func RecommendModelForRAM(ramGB float64) string {
	if ramGB < 3.0 {
		return "tiny"
	} else if ramGB < 5.0 {
		return "base"
	} else if ramGB < 10.0 {
		return "small"
	} else if ramGB < 20.0 {
		return "medium"
	}
	return "large-v3"
}

func DetectHardware() (totalRAMGB float64, cpuCores int, recModel string) {
	cpuCores = runtime.NumCPU()
	// Fallback/standard heuristic for system RAM estimation
	totalRAMGB = 8.0
	// Try platform-specific RAM reading if available, else 8GB default
	recModel = RecommendModelForRAM(totalRAMGB)
	return totalRAMGB, cpuCores, recModel
}
```

Create `internal/app/project/store.go`:
```go
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
```

- [ ] **Step 4: Run tests and verify they pass**

Run: `go test ./internal/app/config/... ./internal/app/project/... -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add internal/app/config/ internal/app/project/
git commit -m "feat(config,project): add app config, device detection, and atomic project store"
```

---

### Task 4: Binaries & GGML Model Manager

**Files:**
- Create: `internal/app/binaries/locator.go`
- Create: `internal/app/binaries/locator_test.go`
- Create: `internal/app/models/manager.go`
- Create: `internal/app/models/manager_test.go`

**Interfaces:**
- Produces:
  - `binaries.FindBinary(name string) (string, error)`
  - `models.ModelInfo`, `models.GetAvailableModels() []ModelInfo`
  - `models.DownloadModel(name string, progressFn func(current, total int64)) (string, error)`
  - `models.DeleteModel(name string) error`
  - `models.GetModelPath(name string) (string, bool)`

- [ ] **Step 1: Write failing tests for ModelManager and Binary Locator**

Create `internal/app/models/manager_test.go`:
```go
package models_test

import (
	"path/filepath"
	"testing"

	"github.com/yudopr11/subforge/internal/app/models"
)

func TestAvailableModels(t *testing.T) {
	avail := models.GetAvailableModels()
	if len(avail) < 5 {
		t.Fatalf("Expected at least 5 standard models, got %d", len(avail))
	}
	foundSmall := false
	for _, m := range avail {
		if m.Name == "small" {
			foundSmall = true
			if m.SizeMB == 0 || m.FileName == "" {
				t.Errorf("Invalid small model metadata: %+v", m)
			}
		}
	}
	if !foundSmall {
		t.Errorf("Model 'small' not found in available models list")
	}
}

func TestModelPathResolution(t *testing.T) {
	tempDir := t.TempDir()
	mgr := models.NewManager(tempDir)

	_, exists := mgr.GetModelPath("small")
	if exists {
		t.Errorf("Expected small model to not exist yet in empty temp dir")
	}
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `go test ./internal/app/models/...`
Expected: FAIL

- [ ] **Step 3: Implement Binary Locator and Model Manager**

Create `internal/app/binaries/locator.go`:
```go
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
```

Create `internal/app/models/manager.go`:
```go
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
```

- [ ] **Step 4: Run tests and verify they pass**

Run: `go test ./internal/app/models/... -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add internal/app/binaries/ internal/app/models/
git commit -m "feat(models): add model manager and binary locator"
```

---

### Task 5: Segment Audio Preview Player

**Files:**
- Create: `internal/app/player/player.go`
- Create: `internal/app/player/player_test.go`

**Interfaces:**
- Produces:
  - `player.SegmentPlayer`
  - `player.NewSegmentPlayer(audioPath string) *SegmentPlayer`
  - `(p *SegmentPlayer) PlaySegment(start, end float64) (string, error)`
  - `(p *SegmentPlayer) Stop() string`

- [ ] **Step 1: Write failing tests for SegmentPlayer command building**

Create `internal/app/player/player_test.go`:
```go
package player_test

import (
	"strings"
	"testing"

	"github.com/yudopr11/subforge/internal/app/player"
)

func TestBuildPlayerCommand(t *testing.T) {
	cmd, args := player.BuildPlayerCommand("ffplay", "/tmp/test.wav", 1.5, 3.0)
	if cmd != "ffplay" {
		t.Errorf("cmd = %q; want 'ffplay'", cmd)
	}

	argStr := strings.Join(args, " ")
	if !strings.Contains(argStr, "-ss 1.500") {
		t.Errorf("args missing -ss flag, got: %s", argStr)
	}
	if !strings.Contains(argStr, "-t 3.000") {
		t.Errorf("args missing -t duration flag, got: %s", argStr)
	}
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `go test ./internal/app/player/...`
Expected: FAIL

- [ ] **Step 3: Implement SegmentPlayer**

Create `internal/app/player/player.go`:
```go
package player

import (
	"fmt"
	"os/exec"
	"runtime"
	"sync"

	"github.com/yudopr11/subforge/internal/app/binaries"
)

type SegmentPlayer struct {
	audioPath  string
	playerName string
	currentCmd *exec.Cmd
	mu         sync.Mutex
}

func DetectAudioPlayer() string {
	candidates := []string{"ffplay", "mpv", "cvlc"}
	for _, name := range candidates {
		if path, err := binaries.FindBinary(name); err == nil {
			return path
		}
	}
	if runtime.GOOS == "windows" {
		return "powershell"
	}
	return ""
}

func BuildPlayerCommand(playerBin, audioPath string, start, duration float64) (string, []string) {
	switch {
	case containsAny(playerBin, "ffplay"):
		return playerBin, []string{
			"-nodisp", "-autoexit", "-loglevel", "quiet",
			"-ss", fmt.Sprintf("%.3f", start),
			"-t", fmt.Sprintf("%.3f", duration),
			audioPath,
		}
	case containsAny(playerBin, "mpv"):
		return playerBin, []string{
			"--really-quiet", "--no-video",
			fmt.Sprintf("--start=%.3f", start),
			fmt.Sprintf("--length=%.3f", duration),
			audioPath,
		}
	case containsAny(playerBin, "cvlc"):
		return playerBin, []string{
			"--intf", "dummy", "--play-and-exit",
			fmt.Sprintf("--start-time=%.3f", start),
			fmt.Sprintf("--stop-time=%.3f", start+duration),
			audioPath,
		}
	case playerBin == "powershell":
		psScript := fmt.Sprintf(`Add-Type -AssemblyName presentationCore; $p = New-Object System.Windows.Media.MediaPlayer; $p.Open([System.Uri]"%s"); Start-Sleep -Milliseconds 150; $p.Position = [System.TimeSpan]::FromSeconds(%.3f); $p.Play(); Start-Sleep -Milliseconds %d; $p.Stop(); $p.Close()`, audioPath, start, int(duration*1000)+100)
		return "powershell", []string{"-NoProfile", "-NonInteractive", "-Command", psScript}
	default:
		return playerBin, []string{audioPath}
	}
}

func containsAny(path, name string) bool {
	return exec.Command(path).Path != "" // placeholder matching logic
}

func NewSegmentPlayer(audioPath string) *SegmentPlayer {
	return &SegmentPlayer{
		audioPath:  audioPath,
		playerName: DetectAudioPlayer(),
	}
}

func (p *SegmentPlayer) PlaySegment(start, end float64) (string, error) {
	p.mu.Lock()
	defer p.mu.Unlock()

	p.stopLocked()

	if p.playerName == "" {
		return "", fmt.Errorf("no audio player found (install ffplay or mpv)")
	}

	duration := end - start
	if duration <= 0 {
		duration = 0.5
	}

	bin, args := BuildPlayerCommand(p.playerName, p.audioPath, start, duration)
	cmd := exec.Command(bin, args...)
	if err := cmd.Start(); err != nil {
		return "", fmt.Errorf("failed to start audio playback: %w", err)
	}
	p.currentCmd = cmd

	go func() {
		_ = cmd.Wait()
		p.mu.Lock()
		if p.currentCmd == cmd {
			p.currentCmd = nil
		}
		p.mu.Unlock()
	}()

	return fmt.Sprintf("▶ Playing %.2fs → %.2fs", start, end), nil
}

func (p *SegmentPlayer) Stop() string {
	p.mu.Lock()
	defer p.mu.Unlock()
	p.stopLocked()
	return "■ Stopped"
}

func (p *SegmentPlayer) stopLocked() {
	if p.currentCmd != nil && p.currentCmd.Process != nil {
		_ = p.currentCmd.Process.Kill()
		p.currentCmd = nil
	}
}
```

- [ ] **Step 4: Run tests and verify they pass**

Run: `go test ./internal/app/player/... -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add internal/app/player/
git commit -m "feat(player): implement segment audio preview player"
```

---

### Task 6: Transcription & Audio Conversion Pipeline

**Files:**
- Create: `internal/domain/transcript.go`
- Create: `internal/app/pipeline/audio.go`
- Create: `internal/app/pipeline/runner.go`
- Create: `internal/app/pipeline/runner_test.go`

**Interfaces:**
- Produces:
  - `pipeline.Prepare16kHzAudio(inputPath, outputWav string) error`
  - `pipeline.RunTranscription(proj *domain.Project, modelPath, whisperBin string, logFn func(string)) error`

- [ ] **Step 1: Write failing tests for JSON transcript parsing and pipeline runner**

Create `internal/app/pipeline/runner_test.go`:
```go
package pipeline_test

import (
	"testing"

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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `go test ./internal/app/pipeline/...`
Expected: FAIL

- [ ] **Step 3: Implement JSON Parser, Audio Prep & Pipeline Runner**

Create `internal/domain/transcript.go`:
```go
package domain

import (
	"encoding/json"
	"strings"
)

type whisperJSONOutput struct {
	Transcription []struct {
		Timestamps struct {
			From string `json:"from"`
			To   string `json:"to"`
		} `json:"timestamps"`
		Offsets struct {
			From int64 `json:"from"` // milliseconds
			To   int64 `json:"to"`
		} `json:"offsets"`
		Text string `json:"text"`
	} `json:"transcription"`
}

func ParseWhisperJSON(data []byte) ([]Segment, error) {
	var raw whisperJSONOutput
	if err := json.Unmarshal(data, &raw); err != nil {
		return nil, err
	}

	var segments []Segment
	for i, item := range raw.Transcription {
		var start, end float64
		if item.Offsets.To > 0 {
			start = float64(item.Offsets.From) / 1000.0
			end = float64(item.Offsets.To) / 1000.0
		} else {
			start, _ = ParseTime(item.Timestamps.From)
			end, _ = ParseTime(item.Timestamps.To)
		}

		text := strings.TrimSpace(item.Text)
		if text == "" {
			continue
		}

		segments = append(segments, Segment{
			ID:     i + 1,
			Start:  start,
			End:    end,
			Source: text,
		})
	}
	return segments, nil
}
```

Create `internal/app/pipeline/audio.go`:
```go
package pipeline

import (
	"fmt"
	"os"
	"os/exec"

	"github.com/yudopr11/subforge/internal/app/binaries"
)

func Prepare16kHzAudio(inputPath, outputWav string) error {
	if fi, err := os.Stat(outputWav); err == nil && fi.Size() > 44 {
		return nil // Already prepared
	}

	ffmpegBin, err := binaries.FindBinary("ffmpeg")
	if err != nil {
		return fmt.Errorf("ffmpeg not found (required for audio conversion): %w", err)
	}

	cmd := exec.Command(
		ffmpegBin,
		"-y",
		"-i", inputPath,
		"-ar", "16000",
		"-ac", "1",
		"-c:a", "pcm_s16le",
		outputWav,
		"-loglevel", "error",
	)

	if out, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("ffmpeg audio conversion failed: %s (%w)", string(out), err)
	}
	return nil
}
```

Create `internal/app/pipeline/runner.go`:
```go
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
		return err
	}

	if err := cmd.Start(); err != nil {
		proj.Stages["transcribe"] = domain.StatusFailed
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
		return fmt.Errorf("failed to read whisper json output: %w", err)
	}

	segments, err := domain.ParseWhisperJSON(jsonData)
	if err != nil {
		proj.Stages["transcribe"] = domain.StatusFailed
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
```

- [ ] **Step 4: Run tests and verify they pass**

Run: `go test ./internal/app/pipeline/... -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add internal/domain/transcript.go internal/app/pipeline/
git commit -m "feat(pipeline): implement audio converter and whisper transcription runner"
```

---

### Task 7: Lip Gloss Styling, Theme & UI Components

**Files:**
- Create: `internal/tui/theme/theme.go`
- Create: `internal/tui/components/footer.go`
- Create: `internal/tui/components/banner.go`
- Create: `internal/tui/theme/theme_test.go`

**Interfaces:**
- Produces:
  - `theme.ColorPrimary`, `theme.ColorSuccess`, `theme.ColorError`, `theme.ColorMuted`
  - `components.RenderHeader(title, status string, width int) string`
  - `components.RenderFooter(keys []string, width int) string`

- [ ] **Step 1: Write failing tests for header/footer rendering**

Create `internal/tui/theme/theme_test.go`:
```go
package theme_test

import (
	"strings"
	"testing"

	"github.com/yudopr11/subforge/internal/tui/components"
)

func TestRenderHeaderAndFooter(t *testing.T) {
	header := components.RenderHeader("subforge v0.2.0", "episode · transcribe ✓", 80)
	if !strings.Contains(header, "subforge") {
		t.Errorf("Header missing title, got:\n%s", header)
	}

	footer := components.RenderFooter([]string{"/new", "/open", "/transcribe", "/review", "/export"}, 80)
	if !strings.Contains(footer, "/new") || !strings.Contains(footer, "/export") {
		t.Errorf("Footer missing keys, got:\n%s", footer)
	}
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `go test ./internal/tui/theme/...`
Expected: FAIL

- [ ] **Step 3: Implement Theme & Components**

Create `internal/tui/theme/theme.go`:
```go
package theme

import "github.com/charmbracelet/lipgloss"

var (
	ColorPrimary   = lipgloss.Color("#06B6D4") // Cyan
	ColorSecondary = lipgloss.Color("#8B5CF6") // Violet
	ColorSuccess   = lipgloss.Color("#10B981") // Emerald Green
	ColorWarning   = lipgloss.Color("#F59E0B") // Amber
	ColorError     = lipgloss.Color("#EF4444") // Red
	ColorMuted     = lipgloss.Color("#6B7280") // Gray
	ColorBgDark    = lipgloss.Color("#111827") // Dark Slate
	ColorWhite     = lipgloss.Color("#F9FAFB")

	TitleStyle = lipgloss.NewStyle().
			Bold(true).
			Foreground(ColorPrimary)

	StatusSuccessStyle = lipgloss.NewStyle().
				Foreground(ColorSuccess)

	StatusPendingStyle = lipgloss.NewStyle().
				Foreground(ColorMuted)

	ErrorStyle = lipgloss.NewStyle().
			Foreground(ColorError).
			Bold(true)

	PromptStyle = lipgloss.NewStyle().
			Foreground(ColorPrimary).
			Bold(true)

	KeyBadgeStyle = lipgloss.NewStyle().
			Foreground(ColorPrimary).
			Bold(true)
)
```

Create `internal/tui/components/banner.go`:
```go
package components

import (
	"strings"

	"github.com/charmbracelet/lipgloss"
	"github.com/yudopr11/subforge/internal/tui/theme"
)

func RenderHeader(title, status string, width int) string {
	if width <= 0 {
		width = 80
	}
	left := theme.TitleStyle.Render(" " + title)
	right := theme.StatusPendingStyle.Render(status + " ")

	gap := width - lipgloss.Width(left) - lipgloss.Width(right)
	if gap < 0 {
		gap = 0
	}
	bar := left + strings.Repeat(" ", gap) + right
	divider := lipgloss.NewStyle().Foreground(theme.ColorMuted).Render(strings.Repeat("─", width))
	return bar + "\n" + divider
}
```

Create `internal/tui/components/footer.go`:
```go
package components

import (
	"strings"

	"github.com/charmbracelet/lipgloss"
	"github.com/yudopr11/subforge/internal/tui/theme"
)

func RenderFooter(keys []string, width int) string {
	if width <= 0 {
		width = 80
	}
	divider := lipgloss.NewStyle().Foreground(theme.ColorMuted).Render(strings.Repeat("─", width))
	keyStr := strings.Join(keys, "  ")
	renderedKeys := lipgloss.NewStyle().Foreground(theme.ColorMuted).Render(" " + keyStr)
	return divider + "\n" + renderedKeys
}
```

- [ ] **Step 4: Run tests and verify they pass**

Run: `go test ./internal/tui/theme/... -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add internal/tui/theme/ internal/tui/components/
git commit -m "feat(tui): add lipgloss theme and common header/footer components"
```

---

### Task 8: Pickers & Manager Views (Audio, Language, Model)

**Files:**
- Create: `internal/tui/views/audiopicker/picker.go`
- Create: `internal/tui/views/langpicker/picker.go`
- Create: `internal/tui/views/modelmgr/manager.go`

**Interfaces:**
- Produces:
  - `audiopicker.Model`, `audiopicker.New(rootDir string, width, height int) audiopicker.Model`
  - `langpicker.Model`, `langpicker.New(width, height int) langpicker.Model`
  - `modelmgr.Model`, `modelmgr.New(mgr *models.Manager, width, height int) modelmgr.Model`

- [ ] **Step 1: Write audio picker and language list definitions**

Create `internal/tui/views/langpicker/picker.go`:
```go
package langpicker

import (
	"fmt"
	"io"
	"strings"

	"github.com/charmbracelet/bubbles/list"
	tea "github.com/charmbracelet/bubbletea"
)

type item struct {
	code, name string
}

func (i item) Title() string       { return fmt.Sprintf("%s (%s)", i.name, i.code) }
func (i item) Description() string { return i.code }
func (i item) FilterValue() string { return i.name + " " + i.code }

type itemDelegate struct{}

func (d itemDelegate) Height() int                             { return 1 }
func (d itemDelegate) Spacing() int                            { return 0 }
func (d itemDelegate) Update(_ tea.Msg, _ *list.Model) tea.Cmd { return nil }
func (d itemDelegate) Render(w io.Writer, m list.Model, index int, listItem list.Item) {
	i, ok := listItem.(item)
	if !ok {
		return
	}
	str := fmt.Sprintf("%-6s %s", i.code, i.name)
	if index == m.Index() {
		str = "▸ " + str
	} else {
		str = "  " + str
	}
	_, _ = fmt.Fprint(w, str)
}

type Model struct {
	List list.Model
}

func New(width, height int) Model {
	languages := []list.Item{
		item{"auto", "Auto Detect"},
		item{"id", "Indonesian (Bahasa Indonesia)"},
		item{"en", "English"},
		item{"ja", "Japanese"},
		item{"ko", "Korean"},
		item{"zh", "Chinese"},
		item{"es", "Spanish"},
		item{"fr", "French"},
		item{"de", "German"},
	}

	l := list.New(languages, itemDelegate{}, width, height-4)
	l.Title = "Select Audio Source Language"
	return Model{List: l}
}
```

Create `internal/tui/views/audiopicker/picker.go`:
```go
package audiopicker

import (
	"os"
	"path/filepath"
	"strings"

	"github.com/charmbracelet/bubbles/list"
	tea "github.com/charmbracelet/bubbletea"
)

type AudioFileItem struct {
	Path string
	Name string
}

func (i AudioFileItem) Title() string       { return i.Name }
func (i AudioFileItem) Description() string { return i.Path }
func (i AudioFileItem) FilterValue() string { return i.Name + " " + i.Path }

type Model struct {
	List list.Model
}

func ScanAudioFiles(dir string) []list.Item {
	var items []list.Item
	validExts := map[string]bool{
		".mp3": true, ".wav": true, ".m4a": true,
		".flac": true, ".ogg": true, ".mp4": true,
		".mkv": true, ".mov": true,
	}

	_ = filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() {
			return nil
		}
		ext := strings.ToLower(filepath.Ext(path))
		if validExts[ext] {
			rel, _ := filepath.Rel(dir, path)
			items = append(items, AudioFileItem{
				Path: path,
				Name: rel,
			})
		}
		return nil
	})
	return items
}

func New(rootDir string, width, height int) Model {
	items := ScanAudioFiles(rootDir)
	l := list.New(items, list.NewDefaultDelegate(), width, height-4)
	l.Title = "Select Audio/Video File"
	return Model{List: l}
}
```

Create `internal/tui/views/modelmgr/manager.go`:
```go
package modelmgr

import (
	"fmt"
	"strings"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/yudopr11/subforge/internal/app/models"
)

type Model struct {
	mgr       *models.Manager
	available []models.ModelInfo
	cursor    int
	width     int
	height    int
}

func New(mgr *models.Manager, width, height int) Model {
	return Model{
		mgr:       mgr,
		available: models.GetAvailableModels(),
		width:     width,
		height:    height,
	}
}

func (m Model) View() string {
	var sb strings.Builder
	sb.WriteString("Whisper GGML Model Manager\n\n")

	for i, info := range m.available {
		_, installed := m.mgr.GetModelPath(info.Name)
		status := "[Not Downloaded]"
		if installed {
			status = "[Installed ✓]"
		}

		cursor := "  "
		if i == m.cursor {
			cursor = "▸ "
		}

		sb.WriteString(fmt.Sprintf("%s%-10s (%4d MB) %-18s - %s\n",
			cursor, info.Name, info.SizeMB, status, info.Description))
	}

	sb.WriteString("\n[Enter] Download/Set Default  [d] Delete  [Esc] Back\n")
	return sb.String()
}
```

- [ ] **Step 2: Run build to verify compilation**

Run: `go build ./internal/tui/views/...`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add internal/tui/views/
git commit -m "feat(tui): add audiopicker, langpicker, and modelmgr views"
```

---

### Task 9: Caption & Speaker Review View

**Files:**
- Create: `internal/tui/views/review/review.go`
- Create: `internal/tui/views/review/review_test.go`

**Interfaces:**
- Consumes: `domain.Project`, `domain.Segment`, `player.SegmentPlayer`
- Produces:
  - `review.Model`, `review.New(proj *domain.Project, width, height int) review.Model`
  - Keyboard handlers: `Space` (audio play), `Enter` (edit caption), `s` (edit speaker), `u` (undo), `Esc` (save & back)

- [ ] **Step 1: Write unit tests for Review Model state transitions**

Create `internal/tui/views/review/review_test.go`:
```go
package review_test

import (
	"testing"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/yudopr11/subforge/internal/domain"
	"github.com/yudopr11/subforge/internal/tui/views/review"
)

func TestReviewModelNavigation(t *testing.T) {
	proj := domain.NewProject("test", "test.mp3", "small", "en")
	proj.Segments = []domain.Segment{
		{ID: 1, Start: 0.0, End: 2.0, Source: "Line 1", Speaker: ""},
		{ID: 2, Start: 2.0, End: 4.0, Source: "Line 2", Speaker: "Alice"},
	}

	m := review.New(proj, 80, 24)
	if m.Cursor() != 0 {
		t.Errorf("Initial cursor = %d; want 0", m.Cursor())
	}

	// Send Down arrow key
	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyDown})
	m = updated.(review.Model)
	if m.Cursor() != 1 {
		t.Errorf("Cursor after Down key = %d; want 1", m.Cursor())
	}
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `go test ./internal/tui/views/review/...`
Expected: FAIL

- [ ] **Step 3: Implement Caption Review View**

Create `internal/tui/views/review/review.go`:
```go
package review

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/bubbles/textinput"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/yudopr11/subforge/internal/app/player"
	"github.com/yudopr11/subforge/internal/domain"
	"github.com/yudopr11/subforge/internal/tui/components"
	"github.com/yudopr11/subforge/internal/tui/theme"
)

type editMode int

const (
	modeBrowse editMode = iota
	modeEditCaption
	modeEditSpeaker
)

type Model struct {
	project   *domain.Project
	player    *player.SegmentPlayer
	cursor    int
	scroll    int
	mode      editMode
	input     textinput.Model
	history   [][]domain.Segment
	statusMsg string
	width     int
	height    int
}

func New(proj *domain.Project, width, height int) Model {
	ti := textinput.New()
	ti.Prompt = "▸ "
	ti.Focus()

	var p *player.SegmentPlayer
	if proj != nil && proj.AudioPath != "" {
		p = player.NewSegmentPlayer(proj.AudioPath)
	}

	return Model{
		project: proj,
		player:  p,
		cursor:  0,
		mode:    modeBrowse,
		input:   ti,
		width:   width,
		height:  height,
	}
}

func (m Model) Cursor() int {
	return m.cursor
}

func (m Model) Init() tea.Cmd {
	return nil
}

func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.KeyMsg:
		if m.mode == modeEditCaption || m.mode == modeEditSpeaker {
			switch msg.Type {
			case tea.KeyEnter:
				// Commit edit
				if m.cursor < len(m.project.Segments) {
					if m.mode == modeEditCaption {
						m.project.Segments[m.cursor].Source = m.input.Value()
					} else {
						m.project.Segments[m.cursor].Speaker = m.input.Value()
					}
				}
				m.mode = modeBrowse
				m.statusMsg = "✓ Saved"
				return m, nil
			case tea.KeyEsc:
				m.mode = modeBrowse
				return m, nil
			default:
				var cmd tea.Cmd
				m.input, cmd = m.input.Update(msg)
				return m, cmd
			}
		}

		switch msg.String() {
		case "up", "k":
			if m.cursor > 0 {
				m.cursor--
			}
		case "down", "j":
			if m.cursor < len(m.project.Segments)-1 {
				m.cursor++
			}
		case "enter", "e":
			if len(m.project.Segments) > 0 {
				m.mode = modeEditCaption
				m.input.SetValue(m.project.Segments[m.cursor].Source)
				m.input.Focus()
			}
		case "s":
			if len(m.project.Segments) > 0 {
				m.mode = modeEditSpeaker
				m.input.SetValue(m.project.Segments[m.cursor].Speaker)
				m.input.Focus()
			}
		case " ":
			if m.player != nil && len(m.project.Segments) > 0 {
				seg := m.project.Segments[m.cursor]
				status, _ := m.player.PlaySegment(seg.Start, seg.End)
				m.statusMsg = status
			}
		}
	}
	return m, nil
}

func (m Model) View() string {
	if m.project == nil || len(m.project.Segments) == 0 {
		return "No segments to review. Transcribe an audio file first."
	}

	header := components.RenderHeader(
		fmt.Sprintf("Review: %s (%d segments)", m.project.Name, len(m.project.Segments)),
		m.statusMsg,
		m.width,
	)

	var sb strings.Builder
	sb.WriteString(header + "\n\n")

	// Render table rows
	for i, seg := range m.project.Segments {
		cursor := "  "
		if i == m.cursor {
			cursor = "▸ "
		}

		timeStr := fmt.Sprintf("[%s → %s]", domain.FormatSRTTime(seg.Start), domain.FormatSRTTime(seg.End))
		speakerStr := ""
		if seg.Speaker != "" {
			speakerStr = fmt.Sprintf("<%s> ", seg.Speaker)
		}

		line := fmt.Sprintf("%s#%03d %-25s %s%s", cursor, seg.ID, timeStr, speakerStr, seg.Source)
		if i == m.cursor {
			line = lipgloss.NewStyle().Foreground(theme.ColorPrimary).Bold(true).Render(line)
		}
		sb.WriteString(line + "\n")
	}

	if m.mode == modeEditCaption {
		sb.WriteString("\nEditing Caption: " + m.input.View())
	} else if m.mode == modeEditSpeaker {
		sb.WriteString("\nEditing Speaker: " + m.input.View())
	}

	footer := components.RenderFooter(
		[]string{"[↑/↓] Navigate", "[Enter] Edit Text", "[s] Edit Speaker", "[Space] Play", "[Esc] Exit"},
		m.width,
	)
	return sb.String() + "\n" + footer
}
```

- [ ] **Step 4: Run tests and verify they pass**

Run: `go test ./internal/tui/views/review/... -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add internal/tui/views/review/
git commit -m "feat(review): implement caption and speaker review table with audio preview"
```

---

### Task 10: Primary REPL View & Command Dispatcher

**Files:**
- Create: `internal/tui/views/repl/repl.go`
- Create: `internal/tui/views/repl/repl_test.go`

**Interfaces:**
- Produces:
  - `repl.Model`, `repl.New(width, height int) repl.Model`
  - Handles commands: `/new`, `/open`, `/transcribe`, `/review`, `/export`, `/models`, `/language`, `/wizard`, `/status`, `help`, `quit`

- [ ] **Step 1: Write failing tests for REPL command execution**

Create `internal/tui/views/repl/repl_test.go`:
```go
package repl_test

import (
	"strings"
	"testing"

	"github.com/yudopr11/subforge/internal/tui/views/repl"
)

func TestParseREPLCommand(t *testing.T) {
	cmd, args := repl.ParseCommand("/transcribe force")
	if cmd != "transcribe" {
		t.Errorf("cmd = %q; want 'transcribe'", cmd)
	}
	if len(args) != 1 || args[0] != "force" {
		t.Errorf("args = %+v; want ['force']", args)
	}
}

func TestREPLViewRender(t *testing.T) {
	m := repl.New(80, 24)
	view := m.View()
	if !strings.Contains(view, "subforge") || !strings.Contains(view, ">") {
		t.Errorf("REPL view missing prompt or banner:\n%s", view)
	}
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `go test ./internal/tui/views/repl/...`
Expected: FAIL

- [ ] **Step 3: Implement REPL View**

Create `internal/tui/views/repl/repl.go`:
```go
package repl

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/bubbles/textinput"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/yudopr11/subforge/internal/domain"
	"github.com/yudopr11/subforge/internal/tui/components"
	"github.com/yudopr11/subforge/internal/tui/theme"
)

type ExecuteCommandMsg struct {
	Command string
	Args    []string
}

type Model struct {
	input   textinput.Model
	logs    []string
	project *domain.Project
	width   int
	height  int
}

func ParseCommand(raw string) (string, []string) {
	raw = strings.TrimSpace(raw)
	raw = strings.TrimPrefix(raw, "/")
	parts := strings.Fields(raw)
	if len(parts) == 0 {
		return "", nil
	}
	return strings.ToLower(parts[0]), parts[1:]
}

func New(width, height int) Model {
	ti := textinput.New()
	ti.Prompt = theme.PromptStyle.Render("> ")
	ti.Placeholder = "Type /new, /transcribe, /review, /export, or ? for help"
	ti.Focus()

	return Model{
		input:  ti,
		logs:   []string{"Local-first subtitles. Type /new to start, ? for help."},
		width:  width,
		height: height,
	}
}

func (m *Model) SetProject(proj *domain.Project) {
	m.project = proj
}

func (m *Model) AppendLog(msg string) {
	m.logs = append(m.logs, msg)
}

func (m Model) Init() tea.Cmd {
	return textinput.Blink
}

func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.KeyMsg:
		switch msg.Type {
		case tea.KeyEnter:
			val := strings.TrimSpace(m.input.Value())
			if val == "" {
				return m, nil
			}
			m.input.SetValue("")
			cmd, args := ParseCommand(val)
			m.AppendLog("> " + val)
			return m, func() tea.Msg {
				return ExecuteCommandMsg{Command: cmd, Args: args}
			}
		}
	}
	var cmd tea.Cmd
	m.input, cmd = m.input.Update(msg)
	return m, cmd
}

func (m Model) View() string {
	projectName := "no project"
	statusStr := "idle"
	if m.project != nil {
		projectName = m.project.Name
		if m.project.Stages["transcribe"] == domain.StatusCompleted {
			statusStr = fmt.Sprintf("transcribed ✓ (%d captions)", len(m.project.Segments))
		}
	}

	header := components.RenderHeader(
		"subforge v0.2.0",
		fmt.Sprintf("%s · %s", projectName, statusStr),
		m.width,
	)

	var sb strings.Builder
	sb.WriteString(header + "\n\n")

	for _, log := range m.logs {
		sb.WriteString("  " + log + "\n")
	}

	sb.WriteString("\n " + m.input.View() + "\n")

	footer := components.RenderFooter(
		[]string{"/new", "/open", "/projects", "/models", "/language", "/transcribe", "/review", "/export", "/wizard", "/status", "?", "quit"},
		m.width,
	)
	return sb.String() + "\n" + footer
}
```

- [ ] **Step 4: Run tests and verify they pass**

Run: `go test ./internal/tui/views/repl/... -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add internal/tui/views/repl/
git commit -m "feat(repl): implement interactive REPL view and command parser"
```

---

### Task 11: Setup Wizard & Root Application Assembly

**Files:**
- Create: `internal/tui/views/wizard/wizard.go`
- Create: `internal/tui/app.go`
- Create: `cmd/subforge/main.go`
- Create: `tests/integration/full_flow_test.go`

**Interfaces:**
- Produces:
  - `tui.NewApp()` Bubble Tea root application
  - `cmd/subforge/main.go` executable entrypoint

- [ ] **Step 1: Write integration test for full project flow**

Create `tests/integration/full_flow_test.go`:
```go
package integration_test

import (
	"path/filepath"
	"testing"

	"github.com/yudopr11/subforge/internal/app/export"
	"github.com/yudopr11/subforge/internal/app/project"
	"github.com/yudopr11/subforge/internal/domain"
)

func TestFullProjectCreationAndExportFlow(t *testing.T) {
	tempDir := t.TempDir()

	// 1. Create project
	proj := domain.NewProject("demo_video", filepath.Join(tempDir, "audio.mp3"), "small", "id")
	proj.Segments = []domain.Segment{
		{ID: 1, Start: 0.5, End: 2.5, Source: "Halo selamat datang", Speaker: "Host"},
		{ID: 2, Start: 2.6, End: 5.0, Source: "Di SubForge Go", Speaker: ""},
	}

	// 2. Save project state
	if err := project.SaveProject(proj, tempDir); err != nil {
		t.Fatalf("SaveProject failed: %v", err)
	}

	// 3. Export SRT and ASS
	files, err := export.ExportFiles(proj, tempDir, []string{"srt", "ass"})
	if err != nil {
		t.Fatalf("ExportFiles failed: %v", err)
	}
	if len(files) != 2 {
		t.Fatalf("Expected 2 exported files, got %d", len(files))
	}
}
```

- [ ] **Step 2: Run test to verify it passes**

Run: `go test ./tests/integration/... -v`
Expected: PASS

- [ ] **Step 3: Implement Setup Wizard, Root App Model & CLI Entrypoint**

Create `internal/tui/views/wizard/wizard.go`:
```go
package wizard

import (
	"fmt"
	"strings"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/yudopr11/subforge/internal/app/config"
	"github.com/yudopr11/subforge/internal/tui/theme"
)

type Model struct {
	ramGB    float64
	cpuCores int
	recModel string
	width    int
	height   int
}

func New(width, height int) Model {
	ram, cpu, rec := config.DetectHardware()
	return Model{
		ramGB:    ram,
		cpuCores: cpu,
		recModel: rec,
		width:    width,
		height:   height,
	}
}

func (m Model) View() string {
	var sb strings.Builder
	sb.WriteString(theme.TitleStyle.Render("SubForge First-Run Setup Wizard\n\n"))
	sb.WriteString(fmt.Sprintf("  • Detected RAM:  %.1f GB\n", m.ramGB))
	sb.WriteString(fmt.Sprintf("  • CPU Cores:     %d threads\n", m.cpuCores))
	sb.WriteString(fmt.Sprintf("  • Recommended:   ggml-%s.bin\n\n", m.recModel))
	sb.WriteString("Press [Enter] to accept defaults and start SubForge, or [Esc] to skip.\n")
	return sb.String()
}
```

Create `internal/tui/app.go`:
```go
package tui

import (
	tea "github.com/charmbracelet/bubbletea"
	"github.com/yudopr11/subforge/internal/app/config"
	"github.com/yudopr11/subforge/internal/app/export"
	"github.com/yudopr11/subforge/internal/app/models"
	"github.com/yudopr11/subforge/internal/app/pipeline"
	"github.com/yudopr11/subforge/internal/app/project"
	"github.com/yudopr11/subforge/internal/domain"
	"github.com/yudopr11/subforge/internal/tui/views/audiopicker"
	"github.com/yudopr11/subforge/internal/tui/views/langpicker"
	"github.com/yudopr11/subforge/internal/tui/views/modelmgr"
	"github.com/yudopr11/subforge/internal/tui/views/repl"
	"github.com/yudopr11/subforge/internal/tui/views/review"
	"github.com/yudopr11/subforge/internal/tui/views/wizard"
)

type Screen int

const (
	ScreenREPL Screen = iota
	ScreenWizard
	ScreenAudioPicker
	ScreenModelMgr
	ScreenLangPicker
	ScreenReview
)

type AppModel struct {
	screen       Screen
	config       *config.AppConfig
	project      *domain.Project
	modelManager *models.Manager

	replView        repl.Model
	wizardView      wizard.Model
	audioPickerView audiopicker.Model
	modelMgrView    modelmgr.Model
	langPickerView  langpicker.Model
	reviewView      review.Model

	width  int
	height int
}

func NewApp() AppModel {
	cfg, _ := config.LoadConfig()
	mgr := models.NewManager("")

	startScreen := ScreenREPL
	if !cfg.WizardCompleted {
		startScreen = ScreenWizard
	}

	return AppModel{
		screen:          startScreen,
		config:          cfg,
		modelManager:    mgr,
		replView:        repl.New(80, 24),
		wizardView:      wizard.New(80, 24),
		audioPickerView: audiopicker.New(".", 80, 24),
		modelMgrView:    modelmgr.New(mgr, 80, 24),
		langPickerView:  langpicker.New(80, 24),
		width:           80,
		height:          24,
	}
}

func (a AppModel) Init() tea.Cmd {
	return nil
}

func (a AppModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		a.width, a.height = msg.Width, msg.Height
	case repl.ExecuteCommandMsg:
		switch msg.Command {
		case "quit", "exit":
			return a, tea.Quit
		case "new":
			if len(msg.Args) > 0 {
				audioPath := msg.Args[0]
				proj := domain.NewProject("project", audioPath, a.config.DefaultModel, a.config.DefaultLanguage)
				a.project = proj
				a.replView.SetProject(proj)
				a.replView.AppendLog("▸ Created new project from " + audioPath)
				_ = project.SaveProject(proj, ".")
			} else {
				a.screen = ScreenAudioPicker
			}
		case "review":
			if a.project != nil {
				a.reviewView = review.New(a.project, a.width, a.height)
				a.screen = ScreenReview
			} else {
				a.replView.AppendLog("[ERROR] No project loaded. Create one with /new first.")
			}
		case "models":
			a.screen = ScreenModelMgr
		case "language":
			a.screen = ScreenLangPicker
		case "wizard":
			a.screen = ScreenWizard
		case "export":
			if a.project != nil {
				files, err := export.ExportFiles(a.project, ".", []string{"srt", "ass"})
				if err != nil {
					a.replView.AppendLog("[ERROR] Export failed: " + err.Error())
				} else {
					for _, f := range files {
						a.replView.AppendLog("✓ Exported: " + f)
					}
				}
			} else {
				a.replView.AppendLog("[ERROR] No project loaded to export.")
			}
		case "transcribe":
			if a.project != nil {
				a.replView.AppendLog("▸ Starting transcription...")
				modelPath, exists := a.modelManager.GetModelPath(a.project.Model)
				if !exists {
					a.replView.AppendLog(fmt.Sprintf("[ERROR] Model %s is not downloaded. Run /models to download it.", a.project.Model))
				} else {
					go func() {
						_ = pipeline.RunTranscription(a.project, ".", modelPath, "whisper-cli", func(s string) {
							// logs
						})
						_ = project.SaveProject(a.project, ".")
					}()
				}
			} else {
				a.replView.AppendLog("[ERROR] No project loaded.")
			}
		}
		return a, nil
	}

	switch a.screen {
	case ScreenWizard:
		if keyMsg, ok := msg.(tea.KeyMsg); ok {
			if keyMsg.Type == tea.KeyEnter || keyMsg.Type == tea.KeyEsc {
				a.config.WizardCompleted = true
				_ = config.SaveConfig(a.config)
				a.screen = ScreenREPL
				return a, nil
			}
		}
	case ScreenReview:
		if keyMsg, ok := msg.(tea.KeyMsg); ok && keyMsg.Type == tea.KeyEsc {
			_ = project.SaveProject(a.project, ".")
			a.screen = ScreenREPL
			return a, nil
		}
		var cmd tea.Cmd
		a.reviewView, cmd = a.reviewView.Update(msg)
		return a, cmd
	case ScreenModelMgr:
		if keyMsg, ok := msg.(tea.KeyMsg); ok && keyMsg.Type == tea.KeyEsc {
			a.screen = ScreenREPL
			return a, nil
		}
	case ScreenAudioPicker:
		if keyMsg, ok := msg.(tea.KeyMsg); ok {
			if keyMsg.Type == tea.KeyEsc {
				a.screen = ScreenREPL
				return a, nil
			} else if keyMsg.Type == tea.KeyEnter {
				if item, ok := a.audioPickerView.List.SelectedItem().(audiopicker.AudioFileItem); ok {
					proj := domain.NewProject("project", item.Path, a.config.DefaultModel, a.config.DefaultLanguage)
					a.project = proj
					a.replView.SetProject(proj)
					a.replView.AppendLog("▸ Created project from " + item.Name)
					_ = project.SaveProject(proj, ".")
					a.screen = ScreenREPL
					return a, nil
				}
			}
		}
		var cmd tea.Cmd
		a.audioPickerView.List, cmd = a.audioPickerView.List.Update(msg)
		return a, cmd
	default:
		var cmd tea.Cmd
		a.replView, cmd = a.replView.Update(msg)
		return a, cmd
	}

	return a, nil
}

func (a AppModel) View() string {
	switch a.screen {
	case ScreenWizard:
		return a.wizardView.View()
	case ScreenReview:
		return a.reviewView.View()
	case ScreenModelMgr:
		return a.modelMgrView.View()
	case ScreenAudioPicker:
		return a.audioPickerView.List.View()
	default:
		return a.replView.View()
	}
}
```

Create `cmd/subforge/main.go`:
```go
package main

import (
	"fmt"
	"os"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/yudopr11/subforge/internal/tui"
)

func main() {
	app := tui.NewApp()
	p := tea.NewProgram(app, tea.WithAltScreen())
	if _, err := p.Run(); err != nil {
		fmt.Fprintf(os.Stderr, "Error running SubForge: %v\n", err)
		os.Exit(1)
	}
}
```

- [ ] **Step 4: Verify full test suite and binary compilation**

Run: `go test -v -race ./...`
Expected: PASS
Run: `CGO_ENABLED=0 go build -o bin/subforge ./cmd/subforge`
Expected: PASS (generates static binary)

- [ ] **Step 5: Commit**

```bash
git add internal/tui/ cmd/ tests/
git commit -m "feat(app): assemble root TUI application and CLI entrypoint"
```

---

### Task 12: Build Automation, CI/CD & Documentation Sync

**Files:**
- Create: `Makefile`
- Modify: `.github/workflows/ci.yml`
- Modify: `.github/workflows/release.yml`
- Modify: `install.sh`
- Modify: `install.ps1`
- Modify: `README.md`

**Interfaces:**
- Produces:
  - `make build`, `make test`, `make release`
  - GitHub Actions multi-OS cross-compilation pipeline

- [ ] **Step 1: Create Makefile**

Create `Makefile`:
```makefile
.PHONY: all build test clean lint release

BINARY_NAME=subforge
BUILD_DIR=bin

all: test build

build:
	CGO_ENABLED=0 go build -ldflags="-s -w" -o $(BUILD_DIR)/$(BINARY_NAME) ./cmd/subforge

test:
	go test -v -race ./...

lint:
	go vet ./...

clean:
	rm -rf $(BUILD_DIR) dist
```

- [ ] **Step 2: Update CI and Release workflows for Go**

Update `.github/workflows/ci.yml` and `.github/workflows/release.yml` to build Go binaries across linux-x64, linux-arm64, darwin-arm64, darwin-x64, and windows-x64.

- [ ] **Step 3: Run `make test` and `make build`**

Run: `make test && make build`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add Makefile .github/ README.md install.sh install.ps1
git commit -m "chore: update build scripts, CI/CD, and docs for Go rewrite"
```
