package domain_test

import (
	"testing"

	"github.com/yudopr11/subforge/internal/domain"
)

func TestParseWhisperJSON_Offsets(t *testing.T) {
	rawJSON := `{
		"transcription": [
			{
				"timestamps": {"from": "00:00:01,000", "to": "00:00:03,500"},
				"offsets": {"from": 1000, "to": 3500},
				"text": " Hello world"
			},
			{
				"timestamps": {"from": "00:00:04,000", "to": "00:00:06,200"},
				"offsets": {"from": 4000, "to": 6200},
				"text": "   "
			},
			{
				"timestamps": {"from": "00:00:07,000", "to": "00:00:09,000"},
				"offsets": {"from": 7000, "to": 9000},
				"text": "SubForge Go"
			}
		]
	}`

	segments, err := domain.ParseWhisperJSON([]byte(rawJSON))
	if err != nil {
		t.Fatalf("ParseWhisperJSON failed: %v", err)
	}

	if len(segments) != 2 {
		t.Fatalf("Expected 2 valid segments (empty segment skipped), got %d", len(segments))
	}

	if segments[0].ID != 1 || segments[0].Source != "Hello world" || segments[0].Start != 1.0 || segments[0].End != 3.5 {
		t.Errorf("Segment[0] mismatch: %+v", segments[0])
	}

	if segments[1].ID != 2 || segments[1].Source != "SubForge Go" || segments[1].Start != 7.0 || segments[1].End != 9.0 {
		t.Errorf("Segment[1] mismatch: %+v", segments[1])
	}
}

func TestParseWhisperJSON_Invalid(t *testing.T) {
	_, err := domain.ParseWhisperJSON([]byte(`{invalid json`))
	if err == nil {
		t.Errorf("Expected error on invalid JSON, got nil")
	}
}
