package theme

import "github.com/charmbracelet/lipgloss"

var (
	ColorPrimary   = lipgloss.Color("#06B6D4") // Cyan
	ColorSecondary = lipgloss.Color("#8B5CF6") // Violet
	ColorSuccess   = lipgloss.Color("#10B981") // Emerald Green
	ColorWarning   = lipgloss.Color("#F59E0B") // Amber
	ColorError     = lipgloss.Color("#EF4444") // Red
	ColorMuted     = lipgloss.Color("#6B7280") // Gray
	ColorBgDark    = lipgloss.Color("#111827") // Dark Slate
	ColorWhite     = lipgloss.Color("#F9FAFB")

	TitleStyle = lipgloss.NewStyle().
			Bold(true).
			Foreground(ColorPrimary)

	StatusSuccessStyle = lipgloss.NewStyle().
				Foreground(ColorSuccess)

	StatusPendingStyle = lipgloss.NewStyle().
				Foreground(ColorMuted)

	ErrorStyle = lipgloss.NewStyle().
			Foreground(ColorError).
			Bold(true)

	PromptStyle = lipgloss.NewStyle().
			Foreground(ColorPrimary).
			Bold(true)

	KeyBadgeStyle = lipgloss.NewStyle().
			Foreground(ColorPrimary).
			Bold(true)
)
