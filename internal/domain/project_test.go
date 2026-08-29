package domain_test

import (
	"encoding/json"
	"testing"
	"time"

	"github.com/yudopr11/subforge/internal/domain"
)

func TestProjectJSONSerialization(t *testing.T) {
	now := time.Date(2026, 8, 29, 12, 0, 0, 0, time.UTC)
	proj := domain.Project{
		Name:      "test_proj",
		AudioPath: "/tmp/audio.mp3",
		Language:  "auto",
		Model:     "small",
		Stages: map[string]domain.StageStatus{
			"transcribe": domain.StatusCompleted,
		},
		Segments: []domain.Segment{
			{ID: 1, Start: 0.0, End: 2.5, Source: "Hello world", Speaker: "Alice"},
			{ID: 2, Start: 2.5, End: 5.0, Source: "SubForge in Go", Speaker: ""},
		},
		CreatedAt: now,
		UpdatedAt: now,
	}

	data, err := json.Marshal(proj)
	if err != nil {
		t.Fatalf("json.Marshal failed: %v", err)
	}

	var decoded domain.Project
	if err := json.Unmarshal(data, &decoded); err != nil {
		t.Fatalf("json.Unmarshal failed: %v", err)
	}

	if decoded.Name != proj.Name {
		t.Errorf("Name = %q; want %q", decoded.Name, proj.Name)
	}
	if len(decoded.Segments) != 2 {
		t.Fatalf("Segments length = %d; want 2", len(decoded.Segments))
	}
	if decoded.Segments[0].Speaker != "Alice" {
		t.Errorf("Segment[0].Speaker = %q; want 'Alice'", decoded.Segments[0].Speaker)
	}
	if decoded.Segments[1].Speaker != "" {
		t.Errorf("Segment[1].Speaker = %q; want ''", decoded.Segments[1].Speaker)
	}
}
