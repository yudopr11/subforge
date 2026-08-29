package langpicker_test

import (
	"strings"
	"testing"

	"github.com/yudopr11/subforge/internal/tui/views/langpicker"
)

func TestLangPickerInitialization(t *testing.T) {
	m := langpicker.New(80, 24)
	items := m.List.Items()
	if len(items) < 5 {
		t.Fatalf("Expected at least 5 languages, got %d", len(items))
	}

	first, ok := items[0].(langpicker.LanguageItem)
	if !ok {
		t.Fatalf("Expected first item to be LanguageItem, got %T", items[0])
	}
	if first.Code != "auto" {
		t.Errorf("First language code = %q; want 'auto'", first.Code)
	}

	if !strings.Contains(first.Title(), "Auto Detect") {
		t.Errorf("Title() missing 'Auto Detect', got %q", first.Title())
	}
	if first.Description() != "auto" {
		t.Errorf("Description() = %q; want 'auto'", first.Description())
	}
	if !strings.Contains(first.FilterValue(), "auto") {
		t.Errorf("FilterValue() missing 'auto', got %q", first.FilterValue())
	}
}
