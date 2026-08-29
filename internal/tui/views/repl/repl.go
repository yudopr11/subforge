package repl

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/bubbles/textinput"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/yudopr11/subforge/internal/domain"
	"github.com/yudopr11/subforge/internal/tui/components"
	"github.com/yudopr11/subforge/internal/tui/theme"
)

type SlashCommand struct {
	Name        string
	Usage       string
	Description string
}

var AvailableCommands = []SlashCommand{
	{Name: "new", Usage: "/new [file]", Description: "Create project (or open audio picker)"},
	{Name: "open", Usage: "/open [path]", Description: "Open existing project (or open project picker)"},
	{Name: "projects", Usage: "/projects", Description: "Browse and switch projects in current folder"},
	{Name: "transcribe", Usage: "/transcribe", Description: "Run local Whisper transcription pipeline"},
	{Name: "review", Usage: "/review", Description: "Open caption & speaker editor with audio preview"},
	{Name: "export", Usage: "/export [srt|ass]", Description: "Export SRT and ASS subtitle files"},
	{Name: "models", Usage: "/models", Description: "Manage, download, and select Whisper GGML models"},
	{Name: "language", Usage: "/language [code]", Description: "Select audio source language (e.g. id, en)"},
	{Name: "wizard", Usage: "/wizard", Description: "Re-run hardware check & setup wizard"},
	{Name: "status", Usage: "/status", Description: "Show active project details and stage status"},
	{Name: "help", Usage: "/help", Description: "Show available commands reference"},
	{Name: "quit", Usage: "/quit", Description: "Exit SubForge application"},
}

func MatchingCommands(input string) []SlashCommand {
	trimmed := strings.TrimSpace(input)
	if !strings.HasPrefix(trimmed, "/") {
		return nil
	}

	parts := strings.Fields(trimmed)
	cmdPart := strings.TrimPrefix(parts[0], "/")
	cmdPart = strings.ToLower(cmdPart)

	var matches []SlashCommand
	for _, cmd := range AvailableCommands {
		if cmdPart == "" || strings.HasPrefix(cmd.Name, cmdPart) {
			matches = append(matches, cmd)
		}
	}
	return matches
}

type ExecuteCommandMsg struct {
	Command string
	Args    []string
}

type Model struct {
	input            textinput.Model
	logs             []string
	project          *domain.Project
	headerCtx        components.HeaderContext
	suggestionCursor int
	width            int
	height           int
}

func ParseCommand(raw string) (string, []string) {
	raw = strings.TrimSpace(raw)
	raw = strings.TrimPrefix(raw, "/")
	parts := strings.Fields(raw)
	if len(parts) == 0 {
		return "", nil
	}
	return strings.ToLower(parts[0]), parts[1:]
}

func New(width, height int) Model {
	ti := textinput.New()
	ti.Prompt = theme.PromptStyle.Render("> ")
	ti.Placeholder = "Type / to see available commands, or ? for help"
	ti.Focus()

	return Model{
		input:            ti,
		logs:             []string{"Local-first subtitles. Type / to see commands, ? for help."},
		headerCtx:        components.HeaderContext{ScreenName: "REPL"},
		suggestionCursor: 0,
		width:            width,
		height:           height,
	}
}

func (m *Model) SetProject(proj *domain.Project) {
	m.project = proj
}

func (m *Model) SetHeaderContext(ctx components.HeaderContext) {
	m.headerCtx = ctx
}

func (m *Model) AppendLog(msg string) {
	msg = strings.TrimSpace(msg)
	if msg == "" {
		return
	}

	// Check if this is an in-place progress update (downloading % or whisper progress %)
	isProgress := strings.HasPrefix(msg, "▸ Downloading ") ||
		strings.Contains(msg, "%") ||
		strings.HasPrefix(msg, "whisper_print_progress:")

	if isProgress && len(m.logs) > 0 {
		last := m.logs[len(m.logs)-1]
		if strings.HasPrefix(last, "▸ Downloading ") ||
			strings.Contains(last, "%") ||
			strings.HasPrefix(last, "whisper_print_progress:") {
			m.logs[len(m.logs)-1] = msg
			return
		}
	}

	m.logs = append(m.logs, msg)
}

func (m Model) Init() tea.Cmd {
	return textinput.Blink
}

func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		return m, nil

	case tea.KeyMsg:
		suggestions := MatchingCommands(m.input.Value())

		if len(suggestions) > 0 {
			switch msg.String() {
			case "tab":
				if m.suggestionCursor >= 0 && m.suggestionCursor < len(suggestions) {
					selected := suggestions[m.suggestionCursor]
					m.input.SetValue("/" + selected.Name + " ")
					m.input.SetCursor(len(m.input.Value()))
					return m, nil
				}
			case "up":
				if m.suggestionCursor > 0 {
					m.suggestionCursor--
					return m, nil
				}
			case "down":
				if m.suggestionCursor < len(suggestions)-1 {
					m.suggestionCursor++
					return m, nil
				}
			case "esc":
				m.input.SetValue("")
				m.suggestionCursor = 0
				return m, nil
			}
		}

		switch msg.Type {
		case tea.KeyEnter:
			val := strings.TrimSpace(m.input.Value())
			if val == "" {
				return m, nil
			}

			// If user typed a partial prefix (e.g. "/t") and didn't finish, auto-complete to top suggestion
			if len(suggestions) > 0 && !strings.Contains(val, " ") {
				if m.suggestionCursor >= 0 && m.suggestionCursor < len(suggestions) {
					val = "/" + suggestions[m.suggestionCursor].Name
				}
			}

			m.input.SetValue("")
			m.suggestionCursor = 0
			cmd, args := ParseCommand(val)
			m.AppendLog("> " + val)
			return m, func() tea.Msg {
				return ExecuteCommandMsg{Command: cmd, Args: args}
			}
		}
	}

	oldVal := m.input.Value()
	var cmd tea.Cmd
	m.input, cmd = m.input.Update(msg)
	if m.input.Value() != oldVal {
		m.suggestionCursor = 0
	}
	return m, cmd
}

func (m Model) View() string {
	width := m.width
	if width <= 0 {
		width = 80
	}
	height := m.height
	if height <= 0 {
		height = 24
	}

	suggestions := MatchingCommands(m.input.Value())

	var sb strings.Builder
	// Reserve space for suggestions popup if active
	suggestionHeight := 0
	if len(suggestions) > 0 {
		suggestionHeight = min(6, len(suggestions)) + 2
	}

	maxLogs := height - 9 - suggestionHeight
	if maxLogs < 2 {
		maxLogs = 2
	}
	startIdx := 0
	if len(m.logs) > maxLogs {
		startIdx = len(m.logs) - maxLogs
	}

	sb.WriteString("\n")
	for i := startIdx; i < len(m.logs); i++ {
		sb.WriteString("  " + m.logs[i] + "\n")
	}

	// Render Suggestions Box if user typed '/'
	if len(suggestions) > 0 {
		sb.WriteString("\n")
		headerText := "  ┌── Suggestions (Tab auto-complete, ↑/↓ navigate) ────────────────"
		if len(headerText) < width-4 {
			headerText += strings.Repeat("─", width-4-len(headerText)) + "┐"
		}
		sb.WriteString(lipgloss.NewStyle().Foreground(theme.ColorMuted).Render(headerText) + "\n")

		maxDisplay := min(6, len(suggestions))
		for i := 0; i < maxDisplay; i++ {
			cmd := suggestions[i]
			cursor := "  │    "
			nameStyle := lipgloss.NewStyle().Foreground(theme.ColorPrimary)
			descStyle := lipgloss.NewStyle().Foreground(theme.ColorMuted)

			if i == m.suggestionCursor {
				cursor = "  │  ▸ "
				nameStyle = nameStyle.Bold(true).Foreground(theme.ColorWhite)
				descStyle = descStyle.Foreground(theme.ColorPrimary)
			}

			usageCol := fmt.Sprintf("%-20s", cmd.Usage)
			line := fmt.Sprintf("%s%s %s", cursor, nameStyle.Render(usageCol), descStyle.Render(cmd.Description))
			sb.WriteString(line + "\n")
		}

		bottomBorder := "  └──" + strings.Repeat("─", width-7) + "┘"
		sb.WriteString(lipgloss.NewStyle().Foreground(theme.ColorMuted).Render(bottomBorder) + "\n")
	}

	sb.WriteString("\n " + m.input.View())

	ctx := m.headerCtx
	if ctx.ScreenName == "" {
		ctx.ScreenName = "REPL"
	}

	return components.RenderScreen(
		ctx,
		sb.String(),
		[]string{"/new", "/open", "/projects", "/models", "/language", "/transcribe", "/review", "/export", "/wizard", "/status", "?", "quit"},
		width,
		height,
	)
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}
