package langpicker

import (
	"fmt"
	"io"

	"github.com/charmbracelet/bubbles/list"
	tea "github.com/charmbracelet/bubbletea"
)

type LanguageItem struct {
	Code string
	Name string
}

func (i LanguageItem) Title() string       { return fmt.Sprintf("%s (%s)", i.Name, i.Code) }
func (i LanguageItem) Description() string { return i.Code }
func (i LanguageItem) FilterValue() string { return i.Name + " " + i.Code }

type itemDelegate struct{}

func (d itemDelegate) Height() int                             { return 1 }
func (d itemDelegate) Spacing() int                            { return 0 }
func (d itemDelegate) Update(_ tea.Msg, _ *list.Model) tea.Cmd { return nil }
func (d itemDelegate) Render(w io.Writer, m list.Model, index int, listItem list.Item) {
	i, ok := listItem.(LanguageItem)
	if !ok {
		return
	}
	str := fmt.Sprintf("%-6s %s", i.Code, i.Name)
	if index == m.Index() {
		str = "▸ " + str
	} else {
		str = "  " + str
	}
	_, _ = fmt.Fprint(w, str)
}

type Model struct {
	List list.Model
}

func New(width, height int) Model {
	languages := []list.Item{
		LanguageItem{"auto", "Auto Detect"},
		LanguageItem{"id", "Indonesian (Bahasa Indonesia)"},
		LanguageItem{"en", "English"},
		LanguageItem{"ja", "Japanese"},
		LanguageItem{"ko", "Korean"},
		LanguageItem{"zh", "Chinese"},
		LanguageItem{"es", "Spanish"},
		LanguageItem{"fr", "French"},
		LanguageItem{"de", "German"},
	}

	h := height - 4
	if h < 0 {
		h = 0
	}
	l := list.New(languages, itemDelegate{}, width, h)
	l.Title = "Select Audio Source Language"
	return Model{List: l}
}
