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
	ramGB    float64
	cpuCores int
	recModel string
	width    int
	height   int
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
		ramGB:    ram,
		cpuCores: cpu,
		recModel: rec,
		width:    width,
		height:   height,
	}
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
	header := components.RenderHeader("First-Run Setup Wizard", "Hardware Detection", m.width)

	var sb strings.Builder
	sb.WriteString(header + "\n\n")
	sb.WriteString(theme.TitleStyle.Render("  SubForge Setup Wizard") + "\n\n")
	sb.WriteString("  Analyzing system hardware capabilities:\n\n")
	sb.WriteString(fmt.Sprintf("  • Detected RAM:       %.1f GB\n", m.ramGB))
	sb.WriteString(fmt.Sprintf("  • CPU Threads:        %d cores\n", m.cpuCores))
	sb.WriteString(fmt.Sprintf("  • Recommended Model:  ggml-%s.bin\n\n", m.recModel))
	sb.WriteString("  SubForge will configure this default model for local transcription.\n")

	footer := components.RenderFooter(
		[]string{"[Enter] Accept Defaults", "[Esc] Skip / Keep Existing"},
		m.width,
	)
	return sb.String() + "\n" + footer
}
