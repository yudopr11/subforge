package modelmgr_test

import (
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/yudopr11/subforge/internal/app/models"
	"github.com/yudopr11/subforge/internal/tui/components"
	"github.com/yudopr11/subforge/internal/tui/views/modelmgr"
)

func TestModelManagerViewAndNavigation(t *testing.T) {
	tempDir := t.TempDir()
	mgr := models.NewManager(tempDir)
	m := modelmgr.New(mgr, 80, 24)

	if m.Cursor() != 0 {
		t.Errorf("Initial cursor = %d; want 0", m.Cursor())
	}

	// Test View rendering
	ctx := components.HeaderContext{
		ScreenName: "Model Manager",
		Model:      "small",
	}
	m.SetHeaderContext(ctx)
	view := m.View()
	if !strings.Contains(view, "Model Manager") {
		t.Errorf("View missing title: %s", view)
	}
	if !strings.Contains(view, "tiny") || !strings.Contains(view, "small") {
		t.Errorf("View missing standard model names: %s", view)
	}

	// Test navigation down
	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyDown})
	m = updated.(modelmgr.Model)
	if m.Cursor() != 1 {
		t.Errorf("Cursor after Down key = %d; want 1", m.Cursor())
	}

	// Test navigation up
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyUp})
	m = updated.(modelmgr.Model)
	if m.Cursor() != 0 {
		t.Errorf("Cursor after Up key = %d; want 0", m.Cursor())
	}

	// Test selected model
	selected := m.SelectedModel()
	if selected == nil || selected.Name != "tiny" {
		t.Errorf("SelectedModel() = %+v; want tiny", selected)
	}
}
