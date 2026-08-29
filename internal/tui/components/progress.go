package components

import (
	"fmt"
	"math"
	"strings"

	"github.com/charmbracelet/lipgloss"
	"github.com/yudopr11/subforge/internal/tui/theme"
)

func FormatProgressBar(label string, current, total int64, width int) string {
	if width <= 0 {
		width = 25
	}
	if width > 30 {
		width = 30
	}

	pct := 0.0
	if total > 0 {
		pct = float64(current) / float64(total)
		if pct > 1.0 {
			pct = 1.0
		}
	}

	filledLen := int(math.Round(pct * float64(width)))
	emptyLen := width - filledLen
	if emptyLen < 0 {
		emptyLen = 0
	}

	bar := lipgloss.NewStyle().Foreground(theme.ColorPrimary).Render(strings.Repeat("█", filledLen)) +
		lipgloss.NewStyle().Foreground(theme.ColorMuted).Render(strings.Repeat("░", emptyLen))

	currMB := float64(current) / (1024 * 1024)
	totMB := float64(total) / (1024 * 1024)

	return fmt.Sprintf("%s [%s] %3.0f%% (%.1f/%.1f MB)", label, bar, pct*100, currMB, totMB)
}

func FormatPercentBar(label string, pct float64, width int) string {
	if width <= 0 {
		width = 25
	}
	if width > 30 {
		width = 30
	}

	if pct > 1.0 && pct <= 100.0 {
		pct = pct / 100.0
	}
	if pct < 0 {
		pct = 0
	}
	if pct > 1.0 {
		pct = 1.0
	}

	filledLen := int(math.Round(pct * float64(width)))
	emptyLen := width - filledLen
	if emptyLen < 0 {
		emptyLen = 0
	}

	bar := lipgloss.NewStyle().Foreground(theme.ColorPrimary).Render(strings.Repeat("█", filledLen)) +
		lipgloss.NewStyle().Foreground(theme.ColorMuted).Render(strings.Repeat("░", emptyLen))

	return fmt.Sprintf("%s [%s] %3.0f%%", label, bar, pct*100)
}
