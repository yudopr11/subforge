package domain

import (
	"fmt"
	"math"
	"strconv"
	"strings"
)

func FormatSRTTime(seconds float64) string {
	if seconds < 0 {
		seconds = 0
	}
	totalMs := int64(math.Round(seconds * 1000.0))
	hours := totalMs / 3600000
	totalMs %= 3600000
	minutes := totalMs / 60000
	totalMs %= 60000
	secs := totalMs / 1000
	ms := totalMs % 1000

	return fmt.Sprintf("%02d:%02d:%02d,%03d", hours, minutes, secs, ms)
}

func FormatASSTime(seconds float64) string {
	if seconds < 0 {
		seconds = 0
	}
	totalCs := int64(math.Floor(seconds * 100.0))
	hours := totalCs / 360000
	totalCs %= 360000
	minutes := totalCs / 6000
	totalCs %= 6000
	secs := totalCs / 100
	cs := totalCs % 100

	return fmt.Sprintf("%d:%02d:%02d.%02d", hours, minutes, secs, cs)
}

func ParseTime(formatted string) (float64, error) {
	formatted = strings.TrimSpace(formatted)
	if strings.Contains(formatted, ",") {
		// SRT format: HH:MM:SS,mmm
		parts := strings.Split(formatted, ",")
		if len(parts) != 2 {
			return 0, fmt.Errorf("invalid srt format: %s", formatted)
		}
		ms, err := strconv.ParseFloat(parts[1], 64)
		if err != nil {
			return 0, err
		}
		timeParts := strings.Split(parts[0], ":")
		if len(timeParts) != 3 {
			return 0, fmt.Errorf("invalid srt time parts: %s", formatted)
		}
		h, _ := strconv.ParseFloat(timeParts[0], 64)
		m, _ := strconv.ParseFloat(timeParts[1], 64)
		s, _ := strconv.ParseFloat(timeParts[2], 64)
		return (h * 3600) + (m * 60) + s + (ms / 1000.0), nil
	} else if strings.Contains(formatted, ".") {
		// ASS format: H:MM:SS.cc
		parts := strings.Split(formatted, ".")
		if len(parts) != 2 {
			return 0, fmt.Errorf("invalid ass format: %s", formatted)
		}
		cs, err := strconv.ParseFloat(parts[1], 64)
		if err != nil {
			return 0, err
		}
		timeParts := strings.Split(parts[0], ":")
		if len(timeParts) != 3 {
			return 0, fmt.Errorf("invalid ass time parts: %s", formatted)
		}
		h, _ := strconv.ParseFloat(timeParts[0], 64)
		m, _ := strconv.ParseFloat(timeParts[1], 64)
		s, _ := strconv.ParseFloat(timeParts[2], 64)
		scale := math.Pow10(len(parts[1]))
		return (h * 3600) + (m * 60) + s + (cs / scale), nil
	}
	return 0, fmt.Errorf("unrecognized timestamp format: %s", formatted)
}
