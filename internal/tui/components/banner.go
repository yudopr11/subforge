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
	if ctx.ScreenName != "" && ctx.ScreenName != "REPL" {
		appTitle = fmt.Sprintf("subforge v0.3.0  •  %s", ctx.ScreenName)
	}

	left1 := theme.TitleStyle.Render(" " + appTitle)
	logoTop := lipgloss.NewStyle().Foreground(theme.ColorPrimary).Bold(true).Render("█▀▀ █▀▀ ")

	gap1 := width - lipgloss.Width(left1) - lipgloss.Width(logoTop)
	if gap1 < 0 {
		gap1 = 0
	}
	topBar := left1 + strings.Repeat(" ", gap1) + logoTop

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
		badges = append(badges, lipgloss.NewStyle().Foreground(theme.ColorPrimary).Bold(true).Render(ctx.Status))
	}

	left2 := " " + strings.Join(badges, "  •  ")
	logoBottom := lipgloss.NewStyle().Foreground(theme.ColorPrimary).Bold(true).Render("▀▀█ █▀  ")

	gap2 := width - lipgloss.Width(left2) - lipgloss.Width(logoBottom)
	if gap2 < 0 {
		// Truncate to first 3 badges if too wide
		left2 = " " + strings.Join(badges[:3], "  •  ")
		gap2 = width - lipgloss.Width(left2) - lipgloss.Width(logoBottom)
		if gap2 < 0 {
			gap2 = 0
		}
	}
	contextLine := left2 + strings.Repeat(" ", gap2) + logoBottom

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
