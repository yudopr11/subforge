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
)

type Model struct {
	project   *domain.Project
	player    *player.SegmentPlayer
	cursor    int
	mode      editMode
	input     textinput.Model
	history   [][]domain.Segment
	statusMsg string
	width     int
	height    int
}

func New(proj *domain.Project, width, height int) Model {
	ti := textinput.New()
	ti.Prompt = "▸ "

	var p *player.SegmentPlayer
	if proj != nil && proj.AudioPath != "" {
		p = player.NewSegmentPlayer(proj.AudioPath)
	}

	if width <= 0 {
		width = 80
	}
	if height <= 0 {
		height = 24
	}

	return Model{
		project: proj,
		player:  p,
		cursor:  0,
		mode:    modeBrowse,
		input:   ti,
		history: make([][]domain.Segment, 0),
		width:   width,
		height:  height,
	}
}

func (m Model) Cursor() int {
	return m.cursor
}

func (m Model) IsEditing() bool {
	return m.mode != modeBrowse
}

func (m *Model) SetSize(width, height int) {
	m.width = width
	m.height = height
}

func (m Model) Init() tea.Cmd {
	return nil
}

func (m *Model) pushHistory() {
	if m.project == nil {
		return
	}
	snap := make([]domain.Segment, len(m.project.Segments))
	copy(snap, m.project.Segments)
	m.history = append(m.history, snap)
}

func (m *Model) popHistory() bool {
	if len(m.history) == 0 || m.project == nil {
		return false
	}
	lastIdx := len(m.history) - 1
	prev := m.history[lastIdx]
	m.history = m.history[:lastIdx]
	m.project.Segments = make([]domain.Segment, len(prev))
	copy(m.project.Segments, prev)
	return true
}

func (m Model) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		return m, nil

	case tea.KeyMsg:
		if m.mode == modeEditCaption || m.mode == modeEditSpeaker {
			switch msg.Type {
			case tea.KeyEnter:
				// Commit edit
				if m.project != nil && m.cursor < len(m.project.Segments) {
					m.pushHistory()
					if m.mode == modeEditCaption {
						m.project.Segments[m.cursor].Source = m.input.Value()
						m.statusMsg = "✓ Caption updated"
					} else {
						m.project.Segments[m.cursor].Speaker = strings.TrimSpace(m.input.Value())
						m.statusMsg = "✓ Speaker updated"
					}
				}
				m.mode = modeBrowse
				m.input.Blur()
				return m, nil

			case tea.KeyEsc:
				// Cancel edit
				m.mode = modeBrowse
				m.input.Blur()
				m.statusMsg = "Edit cancelled"
				return m, nil

			default:
				var cmd tea.Cmd
				m.input, cmd = m.input.Update(msg)
				return m, cmd
			}
		}

		// Browse mode
		switch msg.String() {
		case "up", "k":
			if m.cursor > 0 {
				m.cursor--
			}
		case "down", "j":
			if m.project != nil && m.cursor < len(m.project.Segments)-1 {
				m.cursor++
			}
		case "enter", "e":
			if m.project != nil && len(m.project.Segments) > 0 && m.cursor < len(m.project.Segments) {
				m.mode = modeEditCaption
				m.input.SetValue(m.project.Segments[m.cursor].Source)
				m.input.CursorEnd()
				m.input.Focus()
			}
		case "s":
			if m.project != nil && len(m.project.Segments) > 0 && m.cursor < len(m.project.Segments) {
				m.mode = modeEditSpeaker
				m.input.SetValue(m.project.Segments[m.cursor].Speaker)
				m.input.CursorEnd()
				m.input.Focus()
			}
		case "u", "ctrl+z":
			if m.popHistory() {
				m.statusMsg = "✓ Undone previous edit"
			} else {
				m.statusMsg = "Nothing to undo"
			}
		case " ":
			if m.player != nil && m.project != nil && len(m.project.Segments) > 0 && m.cursor < len(m.project.Segments) {
				seg := m.project.Segments[m.cursor]
				status, err := m.player.PlaySegment(seg.Start, seg.End)
				if err != nil {
					m.statusMsg = "[ERROR] " + err.Error()
				} else {
					m.statusMsg = status
				}
			}
		}
	}
	return m, nil
}

func (m Model) View() string {
	if m.project == nil || len(m.project.Segments) == 0 {
		header := components.RenderHeader("Caption Review", "No segments", m.width)
		body := "\n  No segments to review. Transcribe an audio file first.\n"
		footer := components.RenderFooter([]string{"[Esc] Back"}, m.width)
		return header + body + "\n" + footer
	}

	header := components.RenderHeader(
		fmt.Sprintf("Review: %s (%d segments)", m.project.Name, len(m.project.Segments)),
		m.statusMsg,
		m.width,
	)

	var sb strings.Builder
	sb.WriteString(header + "\n\n")

	// Calculate visible window if terminal height is constrained
	maxRows := m.height - 8
	if maxRows < 5 {
		maxRows = 10
	}

	startIdx := 0
	if m.cursor >= maxRows {
		startIdx = m.cursor - maxRows + 1
	}
	endIdx := startIdx + maxRows
	if endIdx > len(m.project.Segments) {
		endIdx = len(m.project.Segments)
	}

	for i := startIdx; i < endIdx; i++ {
		seg := m.project.Segments[i]
		cursor := "  "
		if i == m.cursor {
			cursor = "▸ "
		}

		timeStr := fmt.Sprintf("[%s → %s]", domain.FormatSRTTime(seg.Start), domain.FormatSRTTime(seg.End))
		speakerStr := ""
		if seg.Speaker != "" {
			speakerStr = fmt.Sprintf("<%s> ", seg.Speaker)
		}

		line := fmt.Sprintf("%s#%03d %-25s %s%s", cursor, seg.ID, timeStr, speakerStr, seg.Source)
		if i == m.cursor {
			line = lipgloss.NewStyle().Foreground(theme.ColorPrimary).Bold(true).Render(line)
		}
		sb.WriteString(line + "\n")
	}

	if m.mode == modeEditCaption {
		sb.WriteString("\n  Editing Caption: " + m.input.View() + "\n")
	} else if m.mode == modeEditSpeaker {
		sb.WriteString("\n  Editing Speaker: " + m.input.View() + "\n")
	}

	footer := components.RenderFooter(
		[]string{"[↑/↓/j/k] Move", "[Enter/e] Edit Caption", "[s] Speaker", "[Space] Play", "[u] Undo", "[Esc] Back"},
		m.width,
	)
	return sb.String() + "\n" + footer
}
