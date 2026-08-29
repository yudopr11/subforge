package wizard_test

import (
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/yudopr11/subforge/internal/tui/views/wizard"
)

func TestWizardModelInitAndView(t *testing.T) {
	m := wizard.New(80, 24)
	if m.RamGB() <= 0 {
		t.Errorf("Expected RamGB > 0, got %f", m.RamGB())
	}
	if m.CPUCores() <= 0 {
		t.Errorf("Expected CPUCores > 0, got %d", m.CPUCores())
	}
	if m.RecModel() == "" {
		t.Errorf("Expected RecModel to be non-empty")
	}

	view := m.View()
	if !strings.Contains(view, "Setup Wizard") {
		t.Errorf("View missing 'Setup Wizard', got:\n%s", view)
	}
	if !strings.Contains(view, "Recommended Model") {
		t.Errorf("View missing 'Recommended Model', got:\n%s", view)
	}

	// Test WindowSizeMsg
	updated, _ := m.Update(tea.WindowSizeMsg{Width: 100, Height: 30})
	m = updated.(wizard.Model)
	if m.Init() != nil {
		t.Errorf("Expected Init() to return nil")
	}
}
