package theme_test

import (
	"strings"
	"testing"

	"github.com/yudopr11/subforge/internal/tui/components"
)

func TestRenderHeaderAndFooter(t *testing.T) {
	header := components.RenderHeader("subforge v0.2.0", "episode · transcribe ✓", 80)
	if !strings.Contains(header, "subforge") {
		t.Errorf("Header missing title, got:\n%s", header)
	}

	footer := components.RenderFooter([]string{"/new", "/open", "/transcribe", "/review", "/export"}, 80)
	if !strings.Contains(footer, "/new") || !strings.Contains(footer, "/export") {
		t.Errorf("Footer missing keys, got:\n%s", footer)
	}
}
