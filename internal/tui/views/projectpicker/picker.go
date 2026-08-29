package projectpicker

import (
	"fmt"
	"io"

	"github.com/charmbracelet/bubbles/list"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/yudopr11/subforge/internal/app/project"
	"github.com/yudopr11/subforge/internal/domain"
	"github.com/yudopr11/subforge/internal/tui/theme"
)

type ProjectItem struct {
	Project *domain.Project
	Path    string
}

func (i ProjectItem) Title() string       { return i.Project.Name }
func (i ProjectItem) Description() string { return i.Path }
func (i ProjectItem) FilterValue() string { return i.Project.Name }

type projectItemDelegate struct{}

func (d projectItemDelegate) Height() int                             { return 1 }
func (d projectItemDelegate) Spacing() int                            { return 0 }
func (d projectItemDelegate) Update(_ tea.Msg, _ *list.Model) tea.Cmd { return nil }
func (d projectItemDelegate) Render(w io.Writer, m list.Model, index int, listItem list.Item) {
	item, ok := listItem.(ProjectItem)
	if !ok || item.Project == nil {
		return
	}

	cursor := "  "
	nameStyle := lipgloss.NewStyle()
	statusStyle := lipgloss.NewStyle().Foreground(theme.ColorMuted)

	if index == m.Index() {
		cursor = "▸ "
		nameStyle = nameStyle.Foreground(theme.ColorPrimary).Bold(true)
	}

	statusText := fmt.Sprintf("(%d captions) [%s]", len(item.Project.Segments), item.Project.Stages["transcribe"])
	line := fmt.Sprintf("%s%-25s %s", cursor, nameStyle.Render(item.Project.Name), statusStyle.Render(statusText))
	_, _ = fmt.Fprint(w, line)
}

type Model struct {
	List list.Model
}

func New(rootDir string, width, height int) Model {
	projects, _ := project.ListProjects(rootDir)

	var items []list.Item
	for _, p := range projects {
		items = append(items, ProjectItem{
			Project: p,
			Path:    rootDir,
		})
	}

	h := height - 4
	if h < 0 {
		h = 0
	}
	l := list.New(items, projectItemDelegate{}, width, h)
	l.Title = "Select Project to Open"
	l.SetShowStatusBar(true)
	l.SetFilteringEnabled(true)
	l.KeyMap.Quit.SetEnabled(false)
	return Model{List: l}
}
