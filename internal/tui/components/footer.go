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
