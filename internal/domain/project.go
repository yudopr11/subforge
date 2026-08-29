package domain

import "time"

type StageStatus string

const (
	StatusPending   StageStatus = "pending"
	StatusRunning   StageStatus = "running"
	StatusCompleted StageStatus = "completed"
	StatusFailed    StageStatus = "failed"
	StatusSkipped   StageStatus = "skipped"
)

type Segment struct {
	ID      int     `json:"id"`
	Start   float64 `json:"start"`
	End     float64 `json:"end"`
	Source  string  `json:"source"`
	Speaker string  `json:"speaker,omitempty"`
}

type Project struct {
	Name          string                 `json:"name"`
	AudioPath     string                 `json:"audio_path"`
	AudioDuration float64                `json:"audio_duration,omitempty"`
	Language      string                 `json:"language"`
	Model         string                 `json:"model"`
	Stages        map[string]StageStatus `json:"stages"`
	Error         string                 `json:"error,omitempty"`
	Segments      []Segment              `json:"segments"`
	CreatedAt     time.Time              `json:"created_at"`
	UpdatedAt     time.Time              `json:"updated_at"`
}

func NewProject(name, audioPath, model, language string) *Project {
	now := time.Now().UTC()
	if language == "" {
		language = "auto"
	}
	if model == "" {
		model = "small"
	}
	return &Project{
		Name:      name,
		AudioPath: audioPath,
		Language:  language,
		Model:     model,
		Stages: map[string]StageStatus{
			"transcribe": StatusPending,
			"export":     StatusPending,
		},
		Segments:  make([]Segment, 0),
		CreatedAt: now,
		UpdatedAt: now,
	}
}
