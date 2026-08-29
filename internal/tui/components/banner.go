package components

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/lipgloss"
	"github.com/yudopr11/subforge/internal/tui/theme"
)

type HeaderContext struct {
	ScreenName  string
	ProjectName string
	ProjectPath string
	Model       string
	Language    string
	Status      string
}

func RenderHeader(ctx HeaderContext, width int) string {
	if width <= 0 {
		width = 80
	}

	appTitle := "subforge v0.3.0"
	screenTitle := ctx.ScreenName
	if screenTitle == "" {
		screenTitle = "REPL"
	}

	left := theme.TitleStyle.Render(" " + appTitle)
	logoBadge := lipgloss.NewStyle().Background(theme.ColorPrimary).Foreground(theme.ColorBgDark).Bold(true).Render(" SF ")
	screenBadge := lipgloss.NewStyle().Foreground(theme.ColorPrimary).Bold(true).Render(" " + screenTitle + " ")
	right := logoBadge + screenBadge

	gap1 := width - lipgloss.Width(left) - lipgloss.Width(right)
	if gap1 < 0 {
		gap1 = 0
	}
	topBar := left + strings.Repeat(" ", gap1) + right

	// Line 2: Context Bar (Project Name, Location, Model, Language, Status)
	projName := ctx.ProjectName
	if projName == "" {
		projName = "(none)"
	}
	projLoc := ctx.ProjectPath
	if projLoc == "" {
		projLoc = "./"
	}

	modelName := ctx.Model
	if modelName == "" {
		modelName = "small"
	}

	langCode := ctx.Language
	if langCode == "" {
		langCode = "auto"
	}

	projBadge := fmt.Sprintf("Project: %s (%s)", projName, projLoc)
	modelBadge := fmt.Sprintf("Model: %s", modelName)
	langBadge := fmt.Sprintf("Lang: %s", langCode)

	var badges []string
	badges = append(badges, lipgloss.NewStyle().Foreground(theme.ColorWhite).Render(projBadge))
	badges = append(badges, lipgloss.NewStyle().Foreground(theme.ColorSecondary).Render(modelBadge))
	badges = append(badges, lipgloss.NewStyle().Foreground(theme.ColorSuccess).Render(langBadge))

	if ctx.Status != "" {
		badges = append(badges, lipgloss.NewStyle().Foreground(theme.ColorMuted).Render(ctx.Status))
	}

	contextLine := " " + strings.Join(badges, "  •  ")
	if lipgloss.Width(contextLine) > width {
		// Truncate cleanly if too wide
		contextLine = " " + strings.Join(badges[:3], "  •  ")
	}

	divider := lipgloss.NewStyle().Foreground(theme.ColorMuted).Render(strings.Repeat("─", width))
	return topBar + "\n" + contextLine + "\n" + divider
}

func RenderScreen(ctx HeaderContext, content string, footerKeys []string, width, height int) string {
	if width <= 0 {
		width = 80
	}
	if height <= 0 {
		height = 24
	}

	header := RenderHeader(ctx, width)
	footer := RenderFooter(footerKeys, width)

	headerHeight := lipgloss.Height(header)
	footerHeight := lipgloss.Height(footer)
	contentHeight := lipgloss.Height(content)

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
