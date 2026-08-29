package tui_test

import (
	"os"
	"path/filepath"
	"testing"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/yudopr11/subforge/internal/domain"
	"github.com/yudopr11/subforge/internal/tui"
	"github.com/yudopr11/subforge/internal/tui/views/repl"
)

func TestAppModelRoutingAndCommands(t *testing.T) {
	t.Cleanup(func() {
		_ = os.Remove("project.json")
		_ = os.Remove("sample.srt")
		_ = os.Remove("sample.ass")
	})

	app := tui.NewApp()

	// 1. Wizard screen navigation
	if app.CurrentScreen() == tui.ScreenWizard {
		// Send Enter to complete wizard
		updated, _ := app.Update(tea.KeyMsg{Type: tea.KeyEnter})
		app = updated.(tui.AppModel)
		if app.CurrentScreen() != tui.ScreenREPL {
			t.Errorf("Screen after Wizard Enter = %v; want ScreenREPL", app.CurrentScreen())
		}
	}

	// 2. Window size msg
	updated, _ := app.Update(tea.WindowSizeMsg{Width: 100, Height: 30})
	app = updated.(tui.AppModel)

	// 3. Command: /new <file>
	tempDir := t.TempDir()
	audioPath := filepath.Join(tempDir, "sample.mp3")
	updated, _ = app.Update(repl.ExecuteCommandMsg{Command: "new", Args: []string{audioPath}})
	app = updated.(tui.AppModel)

	if app.CurrentProject() == nil {
		t.Fatalf("Expected CurrentProject to be set after /new")
	}
	if app.CurrentProject().Name != "sample" {
		t.Errorf("Project Name = %q; want 'sample'", app.CurrentProject().Name)
	}

	// 4. Command: /language en
	updated, _ = app.Update(repl.ExecuteCommandMsg{Command: "language", Args: []string{"en"}})
	app = updated.(tui.AppModel)
	if app.CurrentProject().Language != "en" {
		t.Errorf("Language = %q; want 'en'", app.CurrentProject().Language)
	}

	// 5. Command: /review -> switches to ScreenReview
	app.CurrentProject().Segments = []domain.Segment{
		{ID: 1, Start: 0.0, End: 2.0, Source: "Hello", Speaker: ""},
	}
	updated, _ = app.Update(repl.ExecuteCommandMsg{Command: "review"})
	app = updated.(tui.AppModel)
	if app.CurrentScreen() != tui.ScreenReview {
		t.Errorf("Screen after /review = %v; want ScreenReview", app.CurrentScreen())
	}

	// 5b. Start editing caption (Enter) inside ScreenReview, then press Esc
	// It should cancel edit mode while STAYING on ScreenReview
	updated, _ = app.Update(tea.KeyMsg{Type: tea.KeyEnter})
	app = updated.(tui.AppModel)
	updated, _ = app.Update(tea.KeyMsg{Type: tea.KeyEsc})
	app = updated.(tui.AppModel)
	if app.CurrentScreen() != tui.ScreenReview {
		t.Errorf("Screen after first Esc during editing = %v; want ScreenReview", app.CurrentScreen())
	}

	// 6. Press Esc on Review when not editing -> returns to ScreenREPL
	updated, _ = app.Update(tea.KeyMsg{Type: tea.KeyEsc})
	app = updated.(tui.AppModel)
	if app.CurrentScreen() != tui.ScreenREPL {
		t.Errorf("Screen after Review Esc = %v; want ScreenREPL", app.CurrentScreen())
	}

	// 7. Command: /models -> ScreenModelMgr
	updated, _ = app.Update(repl.ExecuteCommandMsg{Command: "models"})
	app = updated.(tui.AppModel)
	if app.CurrentScreen() != tui.ScreenModelMgr {
		t.Errorf("Screen after /models = %v; want ScreenModelMgr", app.CurrentScreen())
	}

	// Press Esc -> ScreenREPL
	updated, _ = app.Update(tea.KeyMsg{Type: tea.KeyEsc})
	app = updated.(tui.AppModel)
	if app.CurrentScreen() != tui.ScreenREPL {
		t.Errorf("Screen after ModelMgr Esc = %v; want ScreenREPL", app.CurrentScreen())
	}

	// 8. Command: /export
	updated, _ = app.Update(repl.ExecuteCommandMsg{Command: "export"})
	app = updated.(tui.AppModel)
	if app.CurrentProject().Stages["export"] != domain.StatusCompleted {
		t.Errorf("Export stage status = %v; want completed", app.CurrentProject().Stages["export"])
	}

	// 9. Command: quit
	_, cmd := app.Update(repl.ExecuteCommandMsg{Command: "quit"})
	if cmd == nil {
		t.Errorf("Expected tea.Quit command for quit")
	}

	// 10. View rendering check
	view := app.View()
	if len(view) == 0 {
		t.Errorf("Expected non-empty view")
	}
}
