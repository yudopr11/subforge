package audiopicker

import (
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"

	"github.com/charmbracelet/bubbles/list"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/yudopr11/subforge/internal/tui/components"
	"github.com/yudopr11/subforge/internal/tui/theme"
)

type AudioFileItem struct {
	Path string
	Name string
	Size int64
}

func (i AudioFileItem) Title() string       { return i.Name }
func (i AudioFileItem) Description() string { return i.Path }
func (i AudioFileItem) FilterValue() string { return i.Name }

type audioItemDelegate struct{}

func (d audioItemDelegate) Height() int                             { return 1 }
func (d audioItemDelegate) Spacing() int                            { return 0 }
func (d audioItemDelegate) Update(_ tea.Msg, _ *list.Model) tea.Cmd { return nil }
func (d audioItemDelegate) Render(w io.Writer, m list.Model, index int, listItem list.Item) {
	item, ok := listItem.(AudioFileItem)
	if !ok {
		return
	}

	sizeMB := float64(item.Size) / (1024 * 1024)
	sizeStr := fmt.Sprintf("%.1f MB", sizeMB)

	cursor := "  "
	nameStyle := lipgloss.NewStyle()
	sizeStyle := lipgloss.NewStyle().Foreground(theme.ColorMuted)

	if index == m.Index() {
		cursor = "▸ "
		nameStyle = nameStyle.Foreground(theme.ColorPrimary).Bold(true)
	}

	line := fmt.Sprintf("%s%-35s %s", cursor, nameStyle.Render(item.Name), sizeStyle.Render(sizeStr))
	_, _ = fmt.Fprint(w, line)
}

type Model struct {
	List   list.Model
	width  int
	height int
}

func ScanAudioFiles(dir string) []list.Item {
	var items []list.Item
	validExts := map[string]bool{
		".mp3":  true,
		".wav":  true,
		".m4a":  true,
		".flac": true,
		".ogg":  true,
		".mp4":  true,
		".mkv":  true,
		".mov":  true,
	}

	_ = filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() {
			return nil
		}
		ext := strings.ToLower(filepath.Ext(path))
		if validExts[ext] {
			rel, err := filepath.Rel(dir, path)
			if err != nil {
				rel = filepath.Base(path)
			}
			items = append(items, AudioFileItem{
				Path: path,
				Name: rel,
				Size: info.Size(),
			})
		}
		return nil
	})
	return items
}

func New(rootDir string, width, height int) Model {
	items := ScanAudioFiles(rootDir)
	h := height - 6
	if h < 0 {
		h = 0
	}
	l := list.New(items, audioItemDelegate{}, width, h)
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
	header := components.RenderHeader("subforge v0.2.0", "Select Audio File", width)
	footer := components.RenderFooter(
		[]string{"[↑/↓] Navigate", "[Enter] Select Audio", "[/] Filter", "[Esc] Back to REPL"},
		width,
	)
	return header + "\n\n" + m.List.View() + "\n" + footer
}
