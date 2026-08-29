package export

import (
	"fmt"
	"strings"

	"github.com/yudopr11/subforge/internal/domain"
)

func GenerateSRT(segments []domain.Segment) string {
	var sb strings.Builder
	for i, seg := range segments {
		if i > 0 {
			sb.WriteString("\n\n")
		}
		sb.WriteString(fmt.Sprintf("%d\n", seg.ID))
		sb.WriteString(fmt.Sprintf("%s --> %s\n", domain.FormatSRTTime(seg.Start), domain.FormatSRTTime(seg.End)))
		if seg.Speaker != "" {
			sb.WriteString(fmt.Sprintf("[%s]: %s", seg.Speaker, strings.TrimSpace(seg.Source)))
		} else {
			sb.WriteString(strings.TrimSpace(seg.Source))
		}
	}
	sb.WriteString("\n")
	return sb.String()
}
