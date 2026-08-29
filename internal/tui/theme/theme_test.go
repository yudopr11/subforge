package theme_test

import (
	"strings"
	"testing"

	"github.com/yudopr11/subforge/internal/tui/components"
)

func TestRenderHeaderAndScreen(t *testing.T) {
	ctx := components.HeaderContext{
		ScreenName:  "Model Manager",
		ProjectName: "episode_01",
		ProjectPath: "./videos",
		Model:       "small",
		Language:    "id",
		Status:      "transcribed ✓",
	}

	header := components.RenderHeader(ctx, 80)
	if !strings.Contains(header, "subforge v0.3.0") {
		t.Errorf("Header missing title, got:\n%s", header)
	}
	if !strings.Contains(header, "Model Manager") {
		t.Errorf("Header missing screen name, got:\n%s", header)
	}
	if !strings.Contains(header, "episode_01") || !strings.Contains(header, "./videos") {
		t.Errorf("Header missing project metadata, got:\n%s", header)
	}
	if !strings.Contains(header, "small") || !strings.Contains(header, "id") {
		t.Errorf("Header missing model or language metadata, got:\n%s", header)
	}

	screen := components.RenderScreen(ctx, "Content Body", []string{"[Enter] Select", "[Esc] Back"}, 80, 24)
	if !strings.Contains(screen, "Content Body") {
		t.Errorf("Screen missing content, got:\n%s", screen)
	}
}
