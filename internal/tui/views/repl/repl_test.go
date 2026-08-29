package repl_test

import (
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/yudopr11/subforge/internal/domain"
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

	view := m.View()
	if !strings.Contains(view, "custom test log message") {
		t.Errorf("REPL view missing appended log:\n%s", view)
	}
	if !strings.Contains(view, "episode1") {
		t.Errorf("REPL view missing project name:\n%s", view)
	}
	if !strings.Contains(view, "transcribed ✓ (1 captions)") {
		t.Errorf("REPL view missing transcribed status:\n%s", view)
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
