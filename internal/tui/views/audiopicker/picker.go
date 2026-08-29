package audiopicker

import (
	"os"
	"path/filepath"
	"strings"

	"github.com/charmbracelet/bubbles/list"
)

type AudioFileItem struct {
	Path string
	Name string
}

func (i AudioFileItem) Title() string       { return i.Name }
func (i AudioFileItem) Description() string { return i.Path }
func (i AudioFileItem) FilterValue() string { return i.Name + " " + i.Path }

type Model struct {
	List list.Model
}

func ScanAudioFiles(dir string) []list.Item {
	var items []list.Item
	validExts := map[string]bool{
		".mp3":  true,
		".wav":  true,
		".m4a":  true,
		".flac": true,
		".ogg":  true,
		".mp4":  true,
		".mkv":  true,
		".mov":  true,
	}

	_ = filepath.Walk(dir, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() {
			return nil
		}
		ext := strings.ToLower(filepath.Ext(path))
		if validExts[ext] {
			rel, err := filepath.Rel(dir, path)
			if err != nil {
				rel = filepath.Base(path)
			}
			items = append(items, AudioFileItem{
				Path: path,
				Name: rel,
			})
		}
		return nil
	})
	return items
}

func New(rootDir string, width, height int) Model {
	items := ScanAudioFiles(rootDir)
	h := height - 4
	if h < 0 {
		h = 0
	}
	l := list.New(items, list.NewDefaultDelegate(), width, h)
	l.Title = "Select Audio/Video File"
	return Model{List: l}
}
