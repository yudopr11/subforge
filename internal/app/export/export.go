package export

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/yudopr11/subforge/internal/domain"
)

func ExportFiles(proj *domain.Project, outputDir string, formats []string) ([]string, error) {
	if len(formats) == 0 {
		formats = []string{"srt", "ass"}
	}
	if err := os.MkdirAll(outputDir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create output directory: %w", err)
	}

	var generated []string
	baseName := proj.Name
	if baseName == "" {
		baseName = "subtitles"
	}

	for _, fmtType := range formats {
		switch strings.ToLower(fmtType) {
		case "srt":
			content := GenerateSRT(proj.Segments)
			target := filepath.Join(outputDir, baseName+".srt")
			if err := os.WriteFile(target, []byte(content), 0644); err != nil {
				return nil, fmt.Errorf("failed to write SRT file: %w", err)
			}
			generated = append(generated, target)
		case "ass":
			content := GenerateASS(proj.Segments, baseName)
			target := filepath.Join(outputDir, baseName+".ass")
			if err := os.WriteFile(target, []byte(content), 0644); err != nil {
				return nil, fmt.Errorf("failed to write ASS file: %w", err)
			}
			generated = append(generated, target)
		}
	}
	return generated, nil
}
