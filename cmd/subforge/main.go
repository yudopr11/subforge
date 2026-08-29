package main

import (
	"fmt"
	"os"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/yudopr11/subforge/internal/tui"
)

func main() {
	app := tui.NewApp()
	p := tea.NewProgram(app, tea.WithAltScreen())
	if _, err := p.Run(); err != nil {
		fmt.Fprintf(os.Stderr, "Error running SubForge: %v\n", err)
		os.Exit(1)
	}
}
