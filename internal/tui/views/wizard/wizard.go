package wizard

import (
	"fmt"
	"strings"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/yudopr11/subforge/internal/app/config"
	"github.com/yudopr11/subforge/internal/tui/components"
	"github.com/yudopr11/subforge/internal/tui/theme"
)

type Model struct {
	ramGB     float64
	cpuCores  int
	recModel  string
	headerCtx components.HeaderContext
	width     int
	height    int
}

func New(width, height int) Model {
	ram, cpu, rec := config.DetectHardware()
	if width <= 0 {
		width = 80
	}
	if height <= 0 {
		height = 24
	}
	return Model{
		ramGB:     ram,
		cpuCores:  cpu,
		recModel:  rec,
		headerCtx: components.HeaderContext{ScreenName: "Setup Wizard"},
		width:     width,
		height:    height,
	}
}

func (m *Model) SetHeaderContext(ctx components.HeaderContext) {
	m.headerCtx = ctx
}

func (m Model) RamGB() float64 {
	return m.ramGB
}

func (m Model) CPUCores() int {
	return m.cpuCores
}

func (m Model) RecModel() string {
	return m.recModel
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

	var sb strings.Builder
	sb.WriteString("\n" + theme.TitleStyle.Render("  SubForge First-Run Setup Wizard") + "\n\n")
	sb.WriteString("  Analyzing system hardware capabilities:\n\n")
	sb.WriteString(fmt.Sprintf("  • Detected RAM:       %.1f GB\n", m.ramGB))
	sb.WriteString(fmt.Sprintf("  • CPU Threads:        %d cores\n", m.cpuCores))
	sb.WriteString(fmt.Sprintf("  • Recommended Model:  ggml-%s.bin\n\n", m.recModel))
	sb.WriteString("  SubForge will configure this default model for local transcription.\n")

	ctx := m.headerCtx
	if ctx.ScreenName == "" {
		ctx.ScreenName = "Setup Wizard"
	}

	return components.RenderScreen(
		ctx,
		sb.String(),
		[]string{"[Enter] Accept Defaults", "[Esc] Skip / Keep Existing"},
		width,
		height,
	)
}
