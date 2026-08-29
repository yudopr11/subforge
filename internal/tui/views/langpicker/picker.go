package langpicker

import (
	"fmt"
	"io"

	"github.com/charmbracelet/bubbles/list"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/yudopr11/subforge/internal/tui/components"
	"github.com/yudopr11/subforge/internal/tui/theme"
)

type LanguageItem struct {
	Code string
	Name string
}

func (i LanguageItem) Title() string       { return fmt.Sprintf("%s (%s)", i.Name, i.Code) }
func (i LanguageItem) Description() string { return i.Code }
func (i LanguageItem) FilterValue() string { return i.Name + " " + i.Code }

type itemDelegate struct{}

func (d itemDelegate) Height() int                             { return 1 }
func (d itemDelegate) Spacing() int                            { return 0 }
func (d itemDelegate) Update(_ tea.Msg, _ *list.Model) tea.Cmd { return nil }
func (d itemDelegate) Render(w io.Writer, m list.Model, index int, listItem list.Item) {
	i, ok := listItem.(LanguageItem)
	if !ok {
		return
	}
	cursor := "  "
	nameStyle := lipgloss.NewStyle()
	codeStyle := lipgloss.NewStyle().Foreground(theme.ColorMuted)

	if index == m.Index() {
		cursor = "▸ "
		nameStyle = nameStyle.Foreground(theme.ColorPrimary).Bold(true)
	}

	line := fmt.Sprintf("%s%-8s %s", cursor, codeStyle.Render(i.Code), nameStyle.Render(i.Name))
	_, _ = fmt.Fprint(w, line)
}

type Model struct {
	List   list.Model
	width  int
	height int
}

func New(width, height int) Model {
	languages := []list.Item{
		LanguageItem{"auto", "Auto Detect"},
		LanguageItem{"id", "Indonesian (Bahasa Indonesia)"},
		LanguageItem{"en", "English"},
		LanguageItem{"ja", "Japanese"},
		LanguageItem{"ko", "Korean"},
		LanguageItem{"zh", "Chinese"},
		LanguageItem{"es", "Spanish"},
		LanguageItem{"fr", "French"},
		LanguageItem{"de", "German"},
	}

	h := height - 6
	if h < 0 {
		h = 0
	}
	l := list.New(languages, itemDelegate{}, width, h)
	l.SetShowTitle(false)
	l.SetShowHelp(false)
	l.SetShowStatusBar(true)
	l.SetFilteringEnabled(true)
	l.KeyMap.Quit.SetEnabled(false)
	return Model{
		List:   l,
		width:  width,
		height: height,
	}
}

func (m Model) Update(msg tea.Msg) (Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		h := msg.Height - 6
		if h < 0 {
			h = 0
		}
		m.List.SetSize(msg.Width, h)
		return m, nil
	}
	var cmd tea.Cmd
	m.List, cmd = m.List.Update(msg)
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

	return components.RenderScreen(
		"subforge v0.3.0",
		"Language Selector",
		"\n"+m.List.View(),
		[]string{"[↑/↓] Navigate", "[Enter] Select Language", "[/] Filter", "[Esc] Back to REPL"},
		width,
		height,
	)
}
