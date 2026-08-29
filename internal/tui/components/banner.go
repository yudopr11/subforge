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
