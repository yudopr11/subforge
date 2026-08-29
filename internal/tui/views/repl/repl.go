package repl

import (
	"strings"

	"github.com/charmbracelet/bubbles/textinput"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/yudopr11/subforge/internal/domain"
	"github.com/yudopr11/subforge/internal/tui/components"
	"github.com/yudopr11/subforge/internal/tui/theme"
)

type ExecuteCommandMsg struct {
	Command string
	Args    []string
}

type Model struct {
	input     textinput.Model
	logs      []string
	project   *domain.Project
	headerCtx components.HeaderContext
	width     int
	height    int
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
	ti.Placeholder = "Type /new, /transcribe, /review, /export, or ? for help"
	ti.Focus()

	return Model{
		input:     ti,
		logs:      []string{"Local-first subtitles. Type /new to start, ? for help."},
		headerCtx: components.HeaderContext{ScreenName: "REPL"},
		width:     width,
		height:    height,
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
		switch msg.Type {
		case tea.KeyEnter:
			val := strings.TrimSpace(m.input.Value())
			if val == "" {
				return m, nil
			}
			m.input.SetValue("")
			cmd, args := ParseCommand(val)
			m.AppendLog("> " + val)
			return m, func() tea.Msg {
				return ExecuteCommandMsg{Command: cmd, Args: args}
			}
		}
	}
	var cmd tea.Cmd
	m.input, cmd = m.input.Update(msg)
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

	var sb strings.Builder
	maxLogs := height - 9
	if maxLogs < 3 {
		maxLogs = 3
	}
	startIdx := 0
	if len(m.logs) > maxLogs {
		startIdx = len(m.logs) - maxLogs
	}

	sb.WriteString("\n")
	for i := startIdx; i < len(m.logs); i++ {
		sb.WriteString("  " + m.logs[i] + "\n")
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
