package components_test

import (
	"strings"
	"testing"

	"github.com/charmbracelet/lipgloss"
	"github.com/yudopr11/subforge/internal/tui/components"
)

func TestRenderScreenPinnedFooter(t *testing.T) {
	out := components.RenderScreen(
		"subforge v0.3.0",
		"Model Manager",
		"Line 1\nLine 2\nLine 3",
		[]string{"[Enter] Select", "[Esc] Back"},
		80,
		24,
	)

	h := lipgloss.Height(out)
	if h < 24 {
		t.Errorf("Expected total rendered height to be at least 24, got %d", h)
	}

	lines := strings.Split(out, "\n")
	if len(lines) < 24 {
		t.Errorf("Expected at least 24 lines, got %d", len(lines))
	}

	// First line should contain title
	if !strings.Contains(lines[0], "subforge v0.3.0") {
		t.Errorf("First line missing header title: %s", lines[0])
	}

	// Last line should contain footer keybindings
	lastLine := lines[len(lines)-1]
	if !strings.Contains(lastLine, "[Enter] Select") || !strings.Contains(lastLine, "[Esc] Back") {
		t.Errorf("Last line missing footer keys: %s", lastLine)
	}
}
