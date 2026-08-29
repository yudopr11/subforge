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

	if m.InputValue() != "/transcribe " {
		t.Errorf("Expected input to be auto-completed to '/transcribe ', got %q", m.InputValue())
	}
}

func TestREPLSuggestionNavigationWithArrows(t *testing.T) {
	m := repl.New(80, 24)

	// Type '/'
	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'/'}})
	m = updated.(repl.Model)

	// Press Down arrow to navigate to second suggestion ('open')
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyDown})
	m = updated.(repl.Model)

	// Press Down arrow to navigate to third suggestion ('projects')
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyDown})
	m = updated.(repl.Model)

	// Press Up arrow to navigate back to second suggestion ('open')
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyUp})
	m = updated.(repl.Model)

	// Press Tab to auto-complete selected suggestion
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyTab})
	m = updated.(repl.Model)

	if m.InputValue() != "/open " {
		t.Errorf("Expected input to be auto-completed to '/open ', got %q", m.InputValue())
	}
}

func TestREPLSuggestionNavigationEnterToExecute(t *testing.T) {
	m := repl.New(80, 24)

	// Type '/'
	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'/'}})
	m = updated.(repl.Model)

	// Press Down arrow to navigate to second suggestion ('open')
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyDown})
	m = updated.(repl.Model)

	// Press Enter to execute selected suggestion directly
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
	if execMsg.Command != "open" {
		t.Errorf("expected Command 'open', got %q", execMsg.Command)
	}
}

func TestREPLSuggestionToHistoryTransition(t *testing.T) {
	m := repl.New(80, 24)

	// Execute '/status'
	for _, r := range "/status" {
		updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{r}})
		m = updated.(repl.Model)
	}
	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	m = updated.(repl.Model)

	// Type '/' -> suggestions active, cursor at 0
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'/'}})
	m = updated.(repl.Model)

	// Press Down -> moves to cursor 1
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyDown})
	m = updated.(repl.Model)

	// Press Up -> moves back to cursor 0
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyUp})
	m = updated.(repl.Model)

	// Press Up again -> transitions from suggestion 0 into history recall
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyUp})
	m = updated.(repl.Model)
	if m.InputValue() != "/status" {
		t.Errorf("Expected Up at suggestion 0 to restore history '/status', got %q", m.InputValue())
	}

	// Press Down -> restores saved draft '/'
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyDown})
	m = updated.(repl.Model)
	if m.InputValue() != "/" {
		t.Errorf("Expected Down to restore draft '/', got %q", m.InputValue())
	}
}

func TestREPLCommandHistory(t *testing.T) {
	m := repl.New(80, 24)

	// Execute '/new audio.mp3'
	for _, r := range "/new audio.mp3" {
		updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{r}})
		m = updated.(repl.Model)
	}
	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	m = updated.(repl.Model)

	// Execute '/transcribe'
	for _, r := range "/transcribe" {
		updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{r}})
		m = updated.(repl.Model)
	}
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyEnter})
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
	if m.InputValue() != "/review" {
		t.Errorf("Expected Up arrow to restore '/review', got %q", m.InputValue())
	}

	// Press Up arrow again -> should restore '/transcribe'
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyUp})
	m = updated.(repl.Model)
	if m.InputValue() != "/transcribe" {
		t.Errorf("Expected second Up arrow to restore '/transcribe', got %q", m.InputValue())
	}

	// Press Up arrow 3rd time -> should restore '/new audio.mp3'
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyUp})
	m = updated.(repl.Model)
	if m.InputValue() != "/new audio.mp3" {
		t.Errorf("Expected third Up arrow to restore '/new audio.mp3', got %q", m.InputValue())
	}

	// Press Up arrow 4th time -> at beginning of history, stays '/new audio.mp3'
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyUp})
	m = updated.(repl.Model)
	if m.InputValue() != "/new audio.mp3" {
		t.Errorf("Expected fourth Up arrow to stay on '/new audio.mp3', got %q", m.InputValue())
	}

	// Press Down arrow -> should go forward to '/transcribe'
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyDown})
	m = updated.(repl.Model)
	if m.InputValue() != "/transcribe" {
		t.Errorf("Expected Down arrow to go to '/transcribe', got %q", m.InputValue())
	}

	// Press Down arrow -> should go forward to '/review'
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyDown})
	m = updated.(repl.Model)
	if m.InputValue() != "/review" {
		t.Errorf("Expected Down arrow to go to '/review', got %q", m.InputValue())
	}

	// Press Down arrow -> should return to empty buffer
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyDown})
	m = updated.(repl.Model)
	if m.InputValue() != "" {
		t.Errorf("Expected Down arrow to return to empty buffer, got %q", m.InputValue())
	}
}

func TestREPLCommandHistoryWithDraft(t *testing.T) {
	m := repl.New(80, 24)

	// Execute '/status'
	for _, r := range "/status" {
		updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{r}})
		m = updated.(repl.Model)
	}
	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	m = updated.(repl.Model)

	// Type draft '/wizard'
	for _, r := range "/wizard" {
		updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{r}})
		m = updated.(repl.Model)
	}

	// Press Up -> loads '/status' from history, saving draft '/wizard'
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyUp})
	m = updated.(repl.Model)
	if m.InputValue() != "/status" {
		t.Errorf("Expected Up arrow to restore '/status', got %q", m.InputValue())
	}

	// Press Down -> restores saved draft '/wizard'
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyDown})
	m = updated.(repl.Model)
	if m.InputValue() != "/wizard" {
		t.Errorf("Expected Down arrow to restore draft '/wizard', got %q", m.InputValue())
	}
}

func TestREPLEscKeyDismissal(t *testing.T) {
	m := repl.New(80, 24)

	// Type '/transcribe'
	for _, r := range "/transcribe" {
		updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{r}})
		m = updated.(repl.Model)
	}
	if m.InputValue() != "/transcribe" {
		t.Fatalf("Expected input '/transcribe', got %q", m.InputValue())
	}

	// Press Esc -> should clear input
	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyEsc})
	m = updated.(repl.Model)
	if m.InputValue() != "" {
		t.Errorf("Expected input to be cleared after Esc, got %q", m.InputValue())
	}
}

func TestREPLConsecutiveDuplicateHistory(t *testing.T) {
	m := repl.New(80, 24)

	// Execute '/status' twice
	for i := 0; i < 2; i++ {
		for _, r := range "/status" {
			updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{r}})
			m = updated.(repl.Model)
		}
		updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyEnter})
		m = updated.(repl.Model)
	}

	// Execute '/export'
	for _, r := range "/export" {
		updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{r}})
		m = updated.(repl.Model)
	}
	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	m = updated.(repl.Model)

	// Press Up -> '/export'
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyUp})
	m = updated.(repl.Model)
	if m.InputValue() != "/export" {
		t.Errorf("Expected Up arrow to restore '/export', got %q", m.InputValue())
	}

	// Press Up -> should be '/status'
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyUp})
	m = updated.(repl.Model)
	if m.InputValue() != "/status" {
		t.Errorf("Expected Up arrow to restore '/status', got %q", m.InputValue())
	}

	// Press Up again -> should stay '/status' (no duplicate '/status' entry)
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyUp})
	m = updated.(repl.Model)
	if m.InputValue() != "/status" {
		t.Errorf("Expected Up arrow to stay on '/status', got %q", m.InputValue())
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
