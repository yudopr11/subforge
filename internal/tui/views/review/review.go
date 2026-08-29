package review

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/bubbles/textinput"
	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/yudopr11/subforge/internal/app/player"
	"github.com/yudopr11/subforge/internal/domain"
	"github.com/yudopr11/subforge/internal/tui/components"
	"github.com/yudopr11/subforge/internal/tui/theme"
)

type editMode int

const (
	modeBrowse editMode = iota
	modeEditCaption
	modeEditSpeaker
	modeBulkSpeaker
)

type Model struct {
	project   *domain.Project
	player    *player.SegmentPlayer
	cursor    int
	mode      editMode
	input     textinput.Model
	selected  map[int]bool
	history   [][]domain.Segment
	statusMsg string
	headerCtx components.HeaderContext
	width     int
	height    int
}

func New(proj *domain.Project, width, height int) Model {
	ti := textinput.New()
	ti.Prompt = "▸ "
	ti.Focus()

	var p *player.SegmentPlayer
	if proj != nil && proj.AudioPath != "" {
		p = player.NewSegmentPlayer(proj.AudioPath)
	}

	return Model{
		project:   proj,
		player:    p,
		cursor:    0,
		mode:      modeBrowse,
		input:     ti,
		selected:  make(map[int]bool),
		headerCtx: components.HeaderContext{ScreenName: "Caption Review"},
		width:     width,
		height:    height,
	}
}

func (m *Model) SetHeaderContext(ctx components.HeaderContext) {
	m.headerCtx = ctx
}

func (m Model) Cursor() int {
	return m.cursor
}

func (m Model) IsEditing() bool {
	return m.mode != modeBrowse
}

func (m Model) SelectedCount() int {
	count := 0
	for _, sel := range m.selected {
		if sel {
			count++
		}
	}
	return count
}

func (m *Model) StopAudio() {
	if m.player != nil {
		m.player.Stop()
	}
}

func (m Model) Init() tea.Cmd {
	return nil
}

func (m *Model) pushHistory() {
	if m.project == nil {
		return
	}
	snapshot := make([]domain.Segment, len(m.project.Segments))
	copy(snapshot, m.project.Segments)
	m.history = append(m.history, snapshot)
	if len(m.history) > 50 {
		m.history = m.history[1:]
	}
}

func (m *Model) popHistory() bool {
	if len(m.history) == 0 || m.project == nil {
		return false
	}
	last := m.history[len(m.history)-1]
	m.history = m.history[:len(m.history)-1]
	m.project.Segments = make([]domain.Segment, len(last))
	copy(m.project.Segments, last)
	return true
}

func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		return m, nil

	case tea.KeyMsg:
		if m.mode == modeEditCaption || m.mode == modeEditSpeaker || m.mode == modeBulkSpeaker {
			switch msg.Type {
			case tea.KeyEnter:
				val := strings.TrimSpace(m.input.Value())
				if m.mode == modeBulkSpeaker {
					m.pushHistory()
					count := 0
					if m.SelectedCount() > 0 {
						for idx, sel := range m.selected {
							if sel && idx < len(m.project.Segments) {
								m.project.Segments[idx].Speaker = val
								count++
							}
						}
					} else if m.cursor >= 0 && m.cursor < len(m.project.Segments) {
						m.project.Segments[m.cursor].Speaker = val
						count = 1
					}
					m.selected = make(map[int]bool)
					m.mode = modeBrowse
					if val == "" {
						m.statusMsg = fmt.Sprintf("✓ Cleared speaker on %d segment(s)", count)
					} else {
						m.statusMsg = fmt.Sprintf("✓ Set speaker '%s' on %d segment(s)", val, count)
					}
					return m, nil
				}

				if m.cursor >= 0 && m.cursor < len(m.project.Segments) {
					m.pushHistory()
					if m.mode == modeEditCaption {
						m.project.Segments[m.cursor].Source = m.input.Value()
					} else {
						m.project.Segments[m.cursor].Speaker = m.input.Value()
					}
				}
				m.mode = modeBrowse
				m.statusMsg = "✓ Saved"
				return m, nil

			case tea.KeyEsc:
				m.mode = modeBrowse
				m.statusMsg = "Edit cancelled"
				return m, nil

			default:
				var cmd tea.Cmd
				m.input, cmd = m.input.Update(msg)
				return m, cmd
			}
		}

		switch msg.String() {
		case "up", "k":
			if m.cursor > 0 {
				m.cursor--
			}
		case "down", "j":
			if m.project != nil && m.cursor < len(m.project.Segments)-1 {
				m.cursor++
			}
		case "v", "x":
			if m.project != nil && len(m.project.Segments) > 0 {
				m.selected[m.cursor] = !m.selected[m.cursor]
				if !m.selected[m.cursor] {
					delete(m.selected, m.cursor)
				}
				m.statusMsg = fmt.Sprintf("%d segment(s) selected", m.SelectedCount())
			}
		case "a", "ctrl+a":
			if m.project != nil && len(m.project.Segments) > 0 {
				if m.SelectedCount() == len(m.project.Segments) {
					m.selected = make(map[int]bool)
					m.statusMsg = "Cleared selection"
				} else {
					for i := range m.project.Segments {
						m.selected[i] = true
					}
					m.statusMsg = fmt.Sprintf("Selected all %d segments", len(m.project.Segments))
				}
			}
		case "enter", "e":
			if m.project != nil && len(m.project.Segments) > 0 && m.cursor < len(m.project.Segments) {
				m.mode = modeEditCaption
				m.input.SetValue(m.project.Segments[m.cursor].Source)
				m.input.Focus()
			}
		case "s":
			if m.project != nil && len(m.project.Segments) > 0 {
				if m.SelectedCount() > 1 {
					m.mode = modeBulkSpeaker
					m.input.SetValue("")
					m.input.Focus()
				} else if m.cursor < len(m.project.Segments) {
					m.mode = modeEditSpeaker
					m.input.SetValue(m.project.Segments[m.cursor].Speaker)
					m.input.Focus()
				}
			}
		case "S", "b":
			if m.project != nil && len(m.project.Segments) > 0 {
				m.mode = modeBulkSpeaker
				m.input.SetValue("")
				m.input.Focus()
			}
		case "u", "ctrl+z":
			if m.popHistory() {
				m.statusMsg = "↺ Undone"
			}
		case " ":
			if m.player != nil && m.project != nil && len(m.project.Segments) > 0 && m.cursor < len(m.project.Segments) {
				seg := m.project.Segments[m.cursor]
				status, err := m.player.PlaySegment(seg.Start, seg.End)
				if err != nil {
					m.statusMsg = fmt.Sprintf("Error: %v", err)
				} else {
					m.statusMsg = status
				}
			}
		}
	}
	return m, nil
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

	ctx := m.headerCtx
	if ctx.ScreenName == "" {
		ctx.ScreenName = "Caption Review"
	}
	if m.statusMsg != "" {
		ctx.Status = m.statusMsg
	}

	if m.project == nil || len(m.project.Segments) == 0 {
		return components.RenderScreen(
			ctx,
			"\n  No segments to review. Transcribe an audio file first.\n",
			[]string{"[Esc] Back to REPL"},
			width,
			height,
		)
	}

	var sb strings.Builder
	sb.WriteString("\n")

	// Calculate visible window if terminal height is constrained
	maxRows := height - 9
	if maxRows < 4 {
		maxRows = 4
	}

	startIdx := 0
	if m.cursor >= maxRows {
		startIdx = m.cursor - maxRows + 1
	}
	endIdx := startIdx + maxRows
	if endIdx > len(m.project.Segments) {
		endIdx = len(m.project.Segments)
	}

	hasSelections := m.SelectedCount() > 0

	for i := startIdx; i < endIdx; i++ {
		seg := m.project.Segments[i]
		cursor := "  "
		if i == m.cursor {
			cursor = "▸ "
		}

		selectMarker := ""
		if hasSelections {
			if m.selected[i] {
				selectMarker = lipgloss.NewStyle().Foreground(theme.ColorSuccess).Bold(true).Render("[✓] ")
			} else {
				selectMarker = lipgloss.NewStyle().Foreground(theme.ColorMuted).Render("[ ] ")
			}
		}

		timeStr := fmt.Sprintf("[%s → %s]", domain.FormatSRTTime(seg.Start), domain.FormatSRTTime(seg.End))
		speakerStr := ""
		if seg.Speaker != "" {
			speakerStr = lipgloss.NewStyle().Foreground(theme.ColorSecondary).Bold(true).Render(fmt.Sprintf("<%s> ", seg.Speaker))
		}

		line := fmt.Sprintf("%s%s#%03d %-25s %s%s", cursor, selectMarker, seg.ID, timeStr, speakerStr, seg.Source)
		if i == m.cursor {
			line = lipgloss.NewStyle().Foreground(theme.ColorPrimary).Bold(true).Render(line)
		}
		sb.WriteString(line + "\n")
	}

	if m.mode == modeEditCaption {
		sb.WriteString("\n  Editing Caption: " + m.input.View() + "\n")
	} else if m.mode == modeEditSpeaker {
		sb.WriteString("\n  Editing Speaker: " + m.input.View() + "\n")
	} else if m.mode == modeBulkSpeaker {
		count := m.SelectedCount()
		if count == 0 {
			count = 1
		}
		sb.WriteString(fmt.Sprintf("\n  Bulk Speaker Tag for %d segment(s): %s\n", count, m.input.View()))
	}

	footerKeys := []string{"[↑/↓] Move", "[Enter] Edit Text", "[s] Speaker", "[v] Select", "[S] Bulk Speaker", "[Space] Play", "[u] Undo", "[Esc] Back"}
	if hasSelections {
		footerKeys = []string{"[v] Toggle", "[a] Select All", "[S] Apply Speaker", "[u] Undo", "[Esc] Back"}
	}

	return components.RenderScreen(
		ctx,
		sb.String(),
		footerKeys,
		width,
		height,
	)
}
