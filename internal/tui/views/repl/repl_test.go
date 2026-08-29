package repl_test

import (
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/yudopr11/subforge/internal/domain"
	"github.com/yudopr11/subforge/internal/tui/components"
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

func TestParseREPLCommandWithoutSlash(t *testing.T) {
	cmd, args := repl.ParseCommand("review")
	if cmd != "review" {
		t.Errorf("cmd = %q; want 'review'", cmd)
	}
	if len(args) != 0 {
		t.Errorf("args = %+v; want []", args)
	}
}

func TestParseREPLCommandEmpty(t *testing.T) {
	cmd, args := repl.ParseCommand("   ")
	if cmd != "" || len(args) != 0 {
		t.Errorf("expected empty cmd and args, got cmd=%q, args=%+v", cmd, args)
	}
}

func TestREPLViewRender(t *testing.T) {
	m := repl.New(80, 24)
	ctx := components.HeaderContext{
		ScreenName:  "REPL",
		ProjectName: "demo",
		ProjectPath: "./",
		Model:       "small",
		Language:    "auto",
	}
	m.SetHeaderContext(ctx)
	view := m.View()
	if !strings.Contains(view, "subforge") || !strings.Contains(view, ">") {
		t.Errorf("REPL view missing prompt or banner:\n%s", view)
	}
}

func TestREPLAppendLogAndSetProject(t *testing.T) {
	m := repl.New(80, 24)
	m.AppendLog("custom test log message")

	proj := domain.NewProject("episode1", "audio.mp3", "small", "en")
	proj.Stages["transcribe"] = domain.StatusCompleted
	proj.Segments = []domain.Segment{
		{ID: 1, Start: 0.0, End: 2.0, Source: "Hello", Speaker: ""},
	}
	m.SetProject(proj)

	ctx := components.HeaderContext{
		ScreenName:  "REPL",
		ProjectName: "episode1",
		ProjectPath: "./",
		Model:       "small",
		Language:    "en",
		Status:      "transcribed ✓ (1)",
	}
	m.SetHeaderContext(ctx)
	view := m.View()
	if !strings.Contains(view, "custom test log message") {
		t.Errorf("REPL view missing appended log:\n%s", view)
	}
	if !strings.Contains(view, "episode1") {
		t.Errorf("REPL view missing project name:\n%s", view)
	}
}

func TestREPLInPlaceProgressUpdate(t *testing.T) {
	m := repl.New(80, 24)
	m.AppendLog("▸ Downloading medium: 10% (150/1500 MB)")
	m.AppendLog("▸ Downloading medium: 20% (300/1500 MB)")

	ctx := components.HeaderContext{ScreenName: "REPL"}
	m.SetHeaderContext(ctx)
	view := m.View()

	if strings.Contains(view, "10% (150/1500 MB)") {
		t.Errorf("Older progress line was not replaced in-place in log:\n%s", view)
	}
	if !strings.Contains(view, "20% (300/1500 MB)") {
		t.Errorf("Newer progress line missing from log:\n%s", view)
	}
}

func TestREPLEnterKeyCommandExecution(t *testing.T) {
	m := repl.New(80, 24)

	// Send key strokes for '/export srt'
	for _, r := range "/export srt" {
		updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{r}})
		m = updated.(repl.Model)
	}

	// Press Enter
	updated, cmd := m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	m = updated.(repl.Model)

	if cmd == nil {
		t.Fatalf("expected tea.Cmd to be returned on Enter")
	}

	msg := cmd()
	execMsg, ok := msg.(repl.ExecuteCommandMsg)
	if !ok {
		t.Fatalf("expected ExecuteCommandMsg, got %T", msg)
	}

	if execMsg.Command != "export" {
		t.Errorf("Command = %q; want 'export'", execMsg.Command)
	}
	if len(execMsg.Args) != 1 || execMsg.Args[0] != "srt" {
		t.Errorf("Args = %+v; want ['srt']", execMsg.Args)
	}
}

func TestMatchingCommands(t *testing.T) {
	all := repl.MatchingCommands("/")
	if len(all) < 8 {
		t.Errorf("Expected at least 8 commands on '/', got %d", len(all))
	}

	tMatches := repl.MatchingCommands("/t")
	if len(tMatches) != 1 || tMatches[0].Name != "transcribe" {
		t.Errorf("Expected only 'transcribe' on '/t', got %+v", tMatches)
	}

	mMatches := repl.MatchingCommands("/m")
	if len(mMatches) != 1 || mMatches[0].Name != "models" {
		t.Errorf("Expected only 'models' on '/m', got %+v", mMatches)
	}
}

func TestREPLTabAutoComplete(t *testing.T) {
	m := repl.New(80, 24)

	// Type '/t'
	for _, r := range "/t" {
		updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{r}})
		m = updated.(repl.Model)
	}

	// Press Tab
	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyTab})
	m = updated.(repl.Model)

	view := m.View()
	if !strings.Contains(view, "/transcribe") {
		t.Errorf("Expected input to be auto-completed to /transcribe, got:\n%s", view)
	}
}

func TestREPLSuggestionNavigation(t *testing.T) {
	m := repl.New(80, 24)

	// Type '/'
	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'/'}})
	m = updated.(repl.Model)

	// Press Down arrow to navigate to second suggestion
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyDown})
	m = updated.(repl.Model)

	// Press Tab to auto-complete selected suggestion (which is 'open')
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyTab})
	m = updated.(repl.Model)

	view := m.View()
	if !strings.Contains(view, "/open") {
		t.Errorf("Expected input to be auto-completed to /open after Down arrow, got:\n%s", view)
	}
}

func TestREPLCommandHistory(t *testing.T) {
	m := repl.New(80, 24)

	// Execute '/transcribe'
	for _, r := range "/transcribe" {
		updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{r}})
		m = updated.(repl.Model)
	}
	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	m = updated.(repl.Model)

	// Execute '/review'
	for _, r := range "/review" {
		updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{r}})
		m = updated.(repl.Model)
	}
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	m = updated.(repl.Model)

	// Press Up arrow -> should restore '/review'
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyUp})
	m = updated.(repl.Model)
	view := m.View()
	if !strings.Contains(view, "/review") {
		t.Errorf("Expected Up arrow to restore '/review', got view:\n%s", view)
	}

	// Press Up arrow again -> should restore '/transcribe'
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyUp})
	m = updated.(repl.Model)
	view = m.View()
	if !strings.Contains(view, "/transcribe") {
		t.Errorf("Expected second Up arrow to restore '/transcribe', got view:\n%s", view)
	}

	// Press Down arrow -> should go back to '/review'
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyDown})
	m = updated.(repl.Model)
	view = m.View()
	if !strings.Contains(view, "/review") {
		t.Errorf("Expected Down arrow to restore '/review', got view:\n%s", view)
	}
}

func TestREPLWindowSizeMsg(t *testing.T) {
	m := repl.New(80, 24)
	updated, cmd := m.Update(tea.WindowSizeMsg{Width: 100, Height: 30})
	if cmd != nil {
		t.Errorf("expected nil cmd on WindowSizeMsg")
	}
	m = updated.(repl.Model)
	view := m.View()
	if !strings.Contains(view, "subforge") {
		t.Errorf("View missing header after resize")
	}
}
