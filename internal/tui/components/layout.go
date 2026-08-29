package components

import (
	"strings"

	"github.com/charmbracelet/lipgloss"
)

func RenderScreen(headerTitle, headerSubtitle string, content string, footerKeys []string, width, height int) string {
	if width <= 0 {
		width = 80
	}
	if height <= 0 {
		height = 24
	}

	header := RenderHeader(headerTitle, headerSubtitle, width)
	footer := RenderFooter(footerKeys, width)

	headerHeight := lipgloss.Height(header)
	footerHeight := lipgloss.Height(footer)
	contentHeight := lipgloss.Height(content)

	// Available space for padding
	gap := height - headerHeight - footerHeight - contentHeight
	if gap < 0 {
		gap = 0
	}

	padding := ""
	if gap > 0 {
		padding = strings.Repeat("\n", gap)
	}

	return header + "\n" + content + padding + "\n" + footer
}
