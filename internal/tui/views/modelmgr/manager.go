package modelmgr

import (
	"fmt"
	"math"
	"strings"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/yudopr11/subforge/internal/app/models"
	"github.com/yudopr11/subforge/internal/tui/theme"
)

type DownloadProgressMsg struct {
	Model   string
	Current int64
	Total   int64
	NextCmd tea.Cmd
}

type DownloadFinishedMsg struct {
	Model string
	Err   error
}

type ModelSelectedMsg struct {
	Name string
}

type downloadEvent struct {
	Current int64
	Total   int64
	Done    bool
	Err     error
}

func WaitForModelDownload(ch <-chan downloadEvent, modelName string) tea.Cmd {
	return func() tea.Msg {
		event, ok := <-ch
		if !ok || event.Done {
			return DownloadFinishedMsg{Model: modelName, Err: event.Err}
		}
		return DownloadProgressMsg{
			Model:   modelName,
			Current: event.Current,
			Total:   event.Total,
			NextCmd: WaitForModelDownload(ch, modelName),
		}
	}
}

type Model struct {
	mgr             *models.Manager
	available       []models.ModelInfo
	cursor          int
	statusMsg       string
	downloading     bool
	downloadName    string
	downloadCurrent int64
	downloadTotal   int64
	width           int
	height          int
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

func (m Model) IsDownloading() bool {
	return m.downloading
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
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		return m, nil

	case DownloadProgressMsg:
		if m.downloading && m.downloadName == msg.Model {
			m.downloadCurrent = msg.Current
			m.downloadTotal = msg.Total
		}
		return m, msg.NextCmd

	case DownloadFinishedMsg:
		m.downloading = false
		if msg.Err != nil {
			m.statusMsg = theme.ErrorStyle.Render(fmt.Sprintf("Download failed: %v", msg.Err))
		} else {
			m.statusMsg = theme.StatusSuccessStyle.Render(fmt.Sprintf("✓ Model '%s' downloaded successfully! Press Enter to select as active model.", msg.Model))
		}
		return m, nil

	case tea.KeyMsg:
		if m.downloading {
			// Do not accept navigation during active download
			return m, nil
		}

		switch msg.String() {
		case "up", "k":
			if m.cursor > 0 {
				m.cursor--
			}
		case "down", "j":
			if m.cursor < len(m.available)-1 {
				m.cursor++
			}
		case "enter":
			selected := m.SelectedModel()
			if selected == nil || m.mgr == nil {
				return m, nil
			}

			_, installed := m.mgr.GetModelPath(selected.Name)
			if installed {
				// Already installed -> select as active
				return m, func() tea.Msg {
					return ModelSelectedMsg{Name: selected.Name}
				}
			}

			// Not installed -> start async download with progress channel
			m.downloading = true
			m.downloadName = selected.Name
			m.downloadCurrent = 0
			m.downloadTotal = int64(selected.SizeMB) * 1024 * 1024
			m.statusMsg = ""

			modelName := selected.Name
			mgr := m.mgr

			ch := make(chan downloadEvent, 20)
			go func() {
				_, err := mgr.DownloadModel(modelName, func(curr, total int64) {
					ch <- downloadEvent{Current: curr, Total: total}
				})
				ch <- downloadEvent{Done: true, Err: err}
				close(ch)
			}()

			return m, WaitForModelDownload(ch, modelName)

		case "d":
			if selected := m.SelectedModel(); selected != nil && m.mgr != nil {
				err := m.mgr.DeleteModel(selected.Name)
				if err != nil {
					m.statusMsg = theme.ErrorStyle.Render(fmt.Sprintf("Error deleting model: %v", err))
				} else {
					m.statusMsg = fmt.Sprintf("Model %s deleted.", selected.Name)
				}
			}
		}
	}
	return m, nil
}

func (m Model) renderProgressBar(current, total int64, width int) string {
	if width <= 0 {
		width = 30
	}
	if width > 35 {
		width = 35
	}

	pct := 0.0
	if total > 0 {
		pct = float64(current) / float64(total)
		if pct > 1.0 {
			pct = 1.0
		}
	}

	filledLen := int(math.Round(pct * float64(width)))
	emptyLen := width - filledLen
	if emptyLen < 0 {
		emptyLen = 0
	}

	bar := lipgloss.NewStyle().Foreground(theme.ColorPrimary).Render(strings.Repeat("█", filledLen)) +
		lipgloss.NewStyle().Foreground(theme.ColorMuted).Render(strings.Repeat("░", emptyLen))

	currMB := float64(current) / (1024 * 1024)
	totMB := float64(total) / (1024 * 1024)

	return fmt.Sprintf("[%s] %3.0f%% (%.1f / %.1f MB)", bar, pct*100, currMB, totMB)
}

func (m Model) View() string {
	var sb strings.Builder
	sb.WriteString(theme.TitleStyle.Render("Whisper GGML Model Manager\n\n"))

	for i, info := range m.available {
		cursor := "  "
		if i == m.cursor {
			cursor = theme.PromptStyle.Render("▸ ")
		}

		nameStyle := lipgloss.NewStyle().Width(10)
		if i == m.cursor {
			nameStyle = nameStyle.Bold(true).Foreground(theme.ColorPrimary)
		}
		colName := nameStyle.Render(info.Name)

		colSize := fmt.Sprintf("(%4d MB)", info.SizeMB)

		installed := false
		if m.mgr != nil {
			_, installed = m.mgr.GetModelPath(info.Name)
		}

		statusStyle := lipgloss.NewStyle().Width(18)
		var colStatus string
		if installed {
			colStatus = statusStyle.Foreground(theme.ColorSuccess).Render("[Installed ✓]")
		} else {
			colStatus = statusStyle.Foreground(theme.ColorMuted).Render("[Not Downloaded]")
		}

		sb.WriteString(fmt.Sprintf("%s%s %s %s - %s\n",
			cursor, colName, colSize, colStatus, info.Description))
	}

	if m.downloading {
		sb.WriteString("\n" + theme.TitleStyle.Render(fmt.Sprintf("Downloading ggml-%s.bin...", m.downloadName)) + "\n")
		sb.WriteString("  " + m.renderProgressBar(m.downloadCurrent, m.downloadTotal, m.width-25) + "\n")
	} else if m.statusMsg != "" {
		sb.WriteString("\n" + m.statusMsg + "\n")
	}

	if m.downloading {
		sb.WriteString("\nDownloading in progress... Please wait.\n")
	} else {
		sb.WriteString("\n[Enter] Download / Set Active  [d] Delete  [Esc] Back\n")
	}
	return sb.String()
}
