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

	// 3-Line SF ASCII / Block Logo
	logoStyle := lipgloss.NewStyle().Foreground(theme.ColorPrimary).Bold(true)
	logoL1 := logoStyle.Render("█▀▀ █▀▀ ")
	logoL2 := logoStyle.Render("▀▀█ █▀▀ ")
	logoL3 := logoStyle.Render("▀▀▀ ▀   ")

	// Line 1: Title
	left1 := theme.TitleStyle.Render(" " + appTitle)
	gap1 := width - lipgloss.Width(left1) - lipgloss.Width(logoL1)
	if gap1 < 0 {
		gap1 = 0
	}
	line1 := left1 + strings.Repeat(" ", gap1) + logoL1

	// Line 2: Project & Status
	projName := ctx.ProjectName
	if projName == "" {
		projName = "(none)"
	}
	projLoc := ctx.ProjectPath
	if projLoc == "" {
		projLoc = "./"
	}

	projBadge := lipgloss.NewStyle().Foreground(theme.ColorWhite).Render(fmt.Sprintf("Project: %s (%s)", projName, projLoc))
	var line2Badges []string
	line2Badges = append(line2Badges, projBadge)
	if ctx.Status != "" {
		line2Badges = append(line2Badges, lipgloss.NewStyle().Foreground(theme.ColorPrimary).Bold(true).Render(ctx.Status))
	}
	left2 := " " + strings.Join(line2Badges, "  •  ")
	gap2 := width - lipgloss.Width(left2) - lipgloss.Width(logoL2)
	if gap2 < 0 {
		left2 = " " + projBadge
		gap2 = width - lipgloss.Width(left2) - lipgloss.Width(logoL2)
		if gap2 < 0 {
			gap2 = 0
		}
	}
	line2 := left2 + strings.Repeat(" ", gap2) + logoL2

	// Line 3: Model & Language
	modelName := ctx.Model
	if modelName == "" {
		modelName = "small"
	}
	langCode := ctx.Language
	if langCode == "" {
		langCode = "auto"
	}

	modelBadge := lipgloss.NewStyle().Foreground(theme.ColorSecondary).Render(fmt.Sprintf("Model: %s", modelName))
	langBadge := lipgloss.NewStyle().Foreground(theme.ColorSuccess).Render(fmt.Sprintf("Language: %s", langCode))

	left3 := " " + strings.Join([]string{modelBadge, langBadge}, "  •  ")
	gap3 := width - lipgloss.Width(left3) - lipgloss.Width(logoL3)
	if gap3 < 0 {
		gap3 = 0
	}
	line3 := left3 + strings.Repeat(" ", gap3) + logoL3

	// Line 4: Divider
	divider := lipgloss.NewStyle().Foreground(theme.ColorMuted).Render(strings.Repeat("─", width))

	return line1 + "\n" + line2 + "\n" + line3 + "\n" + divider
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
