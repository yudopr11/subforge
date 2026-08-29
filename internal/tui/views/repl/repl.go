package repl

import (
	"fmt"
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
	input   textinput.Model
	logs    []string
	project *domain.Project
	width   int
	height  int
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
		input:  ti,
		logs:   []string{"Local-first subtitles. Type /new to start, ? for help."},
		width:  width,
		height: height,
	}
}

func (m *Model) SetProject(proj *domain.Project) {
	m.project = proj
}

func (m *Model) AppendLog(msg string) {
	m.logs = append(m.logs, msg)
}

func (m Model) Init() tea.Cmd {
	return textinput.Blink
}

func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
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
	projectName := "no project"
	statusStr := "idle"
	if m.project != nil {
		projectName = m.project.Name
		if m.project.Stages != nil && m.project.Stages["transcribe"] == domain.StatusCompleted {
			statusStr = fmt.Sprintf("transcribed ✓ (%d captions)", len(m.project.Segments))
		}
	}

	header := components.RenderHeader(
		"subforge v0.2.0",
		fmt.Sprintf("%s · %s", projectName, statusStr),
		m.width,
	)

	var sb strings.Builder
	sb.WriteString(header + "\n\n")

	for _, log := range m.logs {
		sb.WriteString("  " + log + "\n")
	}

	sb.WriteString("\n " + m.input.View() + "\n")

	footer := components.RenderFooter(
		[]string{"/new", "/open", "/projects", "/models", "/language", "/transcribe", "/review", "/export", "/wizard", "/status", "?", "quit"},
		m.width,
	)
	return sb.String() + "\n" + footer
}
