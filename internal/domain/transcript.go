package domain

import (
	"encoding/json"
	"strings"
)

type whisperJSONOutput struct {
	Transcription []struct {
		Timestamps struct {
			From string `json:"from"`
			To   string `json:"to"`
		} `json:"timestamps"`
		Offsets struct {
			From int64 `json:"from"` // milliseconds
			To   int64 `json:"to"`
		} `json:"offsets"`
		Text string `json:"text"`
	} `json:"transcription"`
}

func ParseWhisperJSON(data []byte) ([]Segment, error) {
	var raw whisperJSONOutput
	if err := json.Unmarshal(data, &raw); err != nil {
		return nil, err
	}

	var segments []Segment
	for _, item := range raw.Transcription {
		var start, end float64
		if item.Offsets.To > 0 {
			start = float64(item.Offsets.From) / 1000.0
			end = float64(item.Offsets.To) / 1000.0
		} else {
			if item.Timestamps.From != "" {
				start, _ = ParseTime(item.Timestamps.From)
			}
			if item.Timestamps.To != "" {
				end, _ = ParseTime(item.Timestamps.To)
			}
		}

		text := strings.TrimSpace(item.Text)
		if text == "" {
			continue
		}

		segments = append(segments, Segment{
			ID:     len(segments) + 1,
			Start:  start,
			End:    end,
			Source: text,
		})
	}
	return segments, nil
}
