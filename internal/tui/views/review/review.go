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
		if m.mode == modeEditCaption || m.mode == modeEditSpeaker {
			switch msg.Type {
			case tea.KeyEnter:
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
		case "enter", "e":
			if m.project != nil && len(m.project.Segments) > 0 && m.cursor < len(m.project.Segments) {
				m.mode = modeEditCaption
				m.input.SetValue(m.project.Segments[m.cursor].Source)
				m.input.Focus()
			}
		case "s":
			if m.project != nil && len(m.project.Segments) > 0 && m.cursor < len(m.project.Segments) {
				m.mode = modeEditSpeaker
				m.input.SetValue(m.project.Segments[m.cursor].Speaker)
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

	return components.RenderScreen(
		ctx,
		sb.String(),
		[]string{"[↑/↓/j/k] Move", "[Enter/e] Edit Caption", "[s] Speaker", "[Space] Play", "[u] Undo", "[Esc] Back to REPL"},
		width,
		height,
	)
}
