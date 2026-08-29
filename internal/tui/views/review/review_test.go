package review_test

import (
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/yudopr11/subforge/internal/domain"
	"github.com/yudopr11/subforge/internal/tui/components"
	"github.com/yudopr11/subforge/internal/tui/views/review"
)

func createTestProject() *domain.Project {
	proj := domain.NewProject("test_project", "test.mp3", "small", "en")
	proj.Segments = []domain.Segment{
		{ID: 1, Start: 0.0, End: 2.5, Source: "First subtitle line", Speaker: "Alice"},
		{ID: 2, Start: 2.5, End: 5.0, Source: "Second subtitle line", Speaker: ""},
		{ID: 3, Start: 5.0, End: 7.5, Source: "Third subtitle line", Speaker: "Bob"},
	}
	return proj
}

func TestReviewModelNavigation(t *testing.T) {
	proj := createTestProject()
	m := review.New(proj, 80, 24)

	if m.Cursor() != 0 {
		t.Errorf("Initial cursor = %d; want 0", m.Cursor())
	}

	// Move down
	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyDown})
	m = updated.(review.Model)
	if m.Cursor() != 1 {
		t.Errorf("Cursor after Down key = %d; want 1", m.Cursor())
	}

	// Move down via 'j'
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'j'}})
	m = updated.(review.Model)
	if m.Cursor() != 2 {
		t.Errorf("Cursor after 'j' = %d; want 2", m.Cursor())
	}

	// Move down past end (should remain at 2)
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyDown})
	m = updated.(review.Model)
	if m.Cursor() != 2 {
		t.Errorf("Cursor after bottom boundary = %d; want 2", m.Cursor())
	}

	// Move up via 'k'
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'k'}})
	m = updated.(review.Model)
	if m.Cursor() != 1 {
		t.Errorf("Cursor after 'k' = %d; want 1", m.Cursor())
	}

	// Move up via Up arrow
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyUp})
	m = updated.(review.Model)
	if m.Cursor() != 0 {
		t.Errorf("Cursor after Up key = %d; want 0", m.Cursor())
	}

	// Move up past top (should remain at 0)
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyUp})
	m = updated.(review.Model)
	if m.Cursor() != 0 {
		t.Errorf("Cursor after top boundary = %d; want 0", m.Cursor())
	}
}

func TestReviewModelEditCaption(t *testing.T) {
	proj := createTestProject()
	m := review.New(proj, 80, 24)

	// Enter edit caption mode with 'enter'
	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	m = updated.(review.Model)

	// Clear and type new text
	// Type '!'
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'!'}})
	m = updated.(review.Model)

	// Commit with enter
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	m = updated.(review.Model)

	if proj.Segments[0].Source != "First subtitle line!" {
		t.Errorf("Updated source = %q; want 'First subtitle line!'", proj.Segments[0].Source)
	}
}

func TestReviewModelEditSpeaker(t *testing.T) {
	proj := createTestProject()
	m := review.New(proj, 80, 24)

	// Enter edit speaker mode with 's'
	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'s'}})
	m = updated.(review.Model)

	// Press right arrow to end of input and type '2'
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'2'}})
	m = updated.(review.Model)

	// Commit with enter
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	m = updated.(review.Model)

	if proj.Segments[0].Speaker != "Alice2" {
		t.Errorf("Updated speaker = %q; want 'Alice2'", proj.Segments[0].Speaker)
	}
}

func TestReviewModelBulkSpeakerTagging(t *testing.T) {
	proj := createTestProject()
	m := review.New(proj, 80, 24)

	// Toggle select row 0 with 'v'
	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'v'}})
	m = updated.(review.Model)
	if m.SelectedCount() != 1 {
		t.Fatalf("Expected 1 selected row, got %d", m.SelectedCount())
	}

	// Move down and select row 1 with 'v'
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyDown})
	m = updated.(review.Model)
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'v'}})
	m = updated.(review.Model)
	if m.SelectedCount() != 2 {
		t.Fatalf("Expected 2 selected rows, got %d", m.SelectedCount())
	}

	// Trigger bulk speaker mode with 'S'
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'S'}})
	m = updated.(review.Model)
	if !m.IsEditing() {
		t.Fatalf("Expected IsEditing() to be true in bulk speaker mode")
	}

	// Type speaker name 'Host'
	for _, r := range "Host" {
		updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{r}})
		m = updated.(review.Model)
	}

	// Commit with Enter
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	m = updated.(review.Model)

	if proj.Segments[0].Speaker != "Host" || proj.Segments[1].Speaker != "Host" {
		t.Errorf("Bulk speaker tag failed: seg[0]=%q, seg[1]=%q; want 'Host'", proj.Segments[0].Speaker, proj.Segments[1].Speaker)
	}
	if m.SelectedCount() != 0 {
		t.Errorf("Expected selections to be cleared after commit, got %d", m.SelectedCount())
	}
}

func TestReviewModelUndo(t *testing.T) {
	proj := createTestProject()
	m := review.New(proj, 80, 24)

	originalText := proj.Segments[0].Source

	// Edit caption
	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	m = updated.(review.Model)
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'?'}})
	m = updated.(review.Model)
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	m = updated.(review.Model)

	if proj.Segments[0].Source == originalText {
		t.Fatalf("Source was not changed before undo")
	}

	// Undo with 'u'
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'u'}})
	m = updated.(review.Model)

	if proj.Segments[0].Source != originalText {
		t.Errorf("After undo, source = %q; want %q", proj.Segments[0].Source, originalText)
	}
}

func TestReviewModelIsEditingAndCancel(t *testing.T) {
	proj := createTestProject()
	m := review.New(proj, 80, 24)

	if m.IsEditing() {
		t.Errorf("Expected IsEditing() to be false initially")
	}

	// Enter edit caption mode
	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyEnter})
	m = updated.(review.Model)

	if !m.IsEditing() {
		t.Errorf("Expected IsEditing() to be true after Enter")
	}

	// Cancel with Esc
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyEsc})
	m = updated.(review.Model)

	if m.IsEditing() {
		t.Errorf("Expected IsEditing() to be false after Esc")
	}

	// Enter edit speaker mode with 's'
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'s'}})
	m = updated.(review.Model)

	if !m.IsEditing() {
		t.Errorf("Expected IsEditing() to be true in speaker mode")
	}

	// Cancel with Esc
	updated, _ = m.Update(tea.KeyMsg{Type: tea.KeyEsc})
	m = updated.(review.Model)

	if m.IsEditing() {
		t.Errorf("Expected IsEditing() to be false after Esc")
	}
}

func TestReviewModelView(t *testing.T) {
	proj := createTestProject()
	m := review.New(proj, 80, 24)

	ctx := components.HeaderContext{
		ScreenName:  "Caption Review",
		ProjectName: proj.Name,
		Model:       "small",
	}
	m.SetHeaderContext(ctx)
	view := m.View()
	if !strings.Contains(view, "First subtitle line") {
		t.Errorf("View missing segment text, got:\n%s", view)
	}
	if !strings.Contains(view, "<Alice>") {
		t.Errorf("View missing speaker tag, got:\n%s", view)
	}
	if !strings.Contains(view, "[Space] Play") {
		t.Errorf("View missing footer keybinding hint, got:\n%s", view)
	}
}
