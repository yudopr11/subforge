package modelmgr

import (
	"fmt"
	"strings"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/yudopr11/subforge/internal/app/models"
)

type Model struct {
	mgr       *models.Manager
	available []models.ModelInfo
	cursor    int
	statusMsg string
	width     int
	height    int
}

func New(mgr *models.Manager, width, height int) Model {
	return Model{
		mgr:       mgr,
		available: models.GetAvailableModels(),
		cursor:    0,
		width:     width,
		height:    height,
	}
}

func (m Model) Cursor() int {
	return m.cursor
}

func (m Model) SelectedModel() *models.ModelInfo {
	if m.cursor >= 0 && m.cursor < len(m.available) {
		return &m.available[m.cursor]
	}
	return nil
}

func (m Model) Init() tea.Cmd {
	return nil
}

func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.KeyMsg:
		switch msg.String() {
		case "up", "k":
			if m.cursor > 0 {
				m.cursor--
			}
		case "down", "j":
			if m.cursor < len(m.available)-1 {
				m.cursor++
			}
		case "d":
			if selected := m.SelectedModel(); selected != nil && m.mgr != nil {
				err := m.mgr.DeleteModel(selected.Name)
				if err != nil {
					m.statusMsg = fmt.Sprintf("Error deleting model: %v", err)
				} else {
					m.statusMsg = fmt.Sprintf("Model %s deleted.", selected.Name)
				}
			}
		}
	}
	return m, nil
}

func (m Model) View() string {
	var sb strings.Builder
	sb.WriteString("Whisper GGML Model Manager\n\n")

	for i, info := range m.available {
		status := "[Not Downloaded]"
		if m.mgr != nil {
			if _, installed := m.mgr.GetModelPath(info.Name); installed {
				status = "[Installed ✓]"
			}
		}

		cursor := "  "
		if i == m.cursor {
			cursor = "▸ "
		}

		sb.WriteString(fmt.Sprintf("%s%-10s (%4d MB) %-18s - %s\n",
			cursor, info.Name, info.SizeMB, status, info.Description))
	}

	if m.statusMsg != "" {
		sb.WriteString("\n" + m.statusMsg + "\n")
	}

	sb.WriteString("\n[Enter] Download/Set Default  [d] Delete  [Esc] Back\n")
	return sb.String()
}
