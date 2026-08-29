package domain_test

import (
	"math"
	"testing"

	"github.com/yudopr11/subforge/internal/domain"
)

func TestFormatSRTTime(t *testing.T) {
	tests := []struct {
		input    float64
		expected string
	}{
		{0.0, "00:00:00,000"},
		{1.234, "00:00:01,234"},
		{65.5, "00:01:05,500"},
		{3661.089, "01:01:01,089"},
	}

	for _, tt := range tests {
		got := domain.FormatSRTTime(tt.input)
		if got != tt.expected {
			t.Errorf("FormatSRTTime(%f) = %q; want %q", tt.input, got, tt.expected)
		}
	}
}

func TestFormatASSTime(t *testing.T) {
	tests := []struct {
		input    float64
		expected string
	}{
		{0.0, "0:00:00.00"},
		{1.234, "0:00:01.23"},
		{65.5, "0:01:05.50"},
		{3661.089, "1:01:01.08"},
	}

	for _, tt := range tests {
		got := domain.FormatASSTime(tt.input)
		if got != tt.expected {
			t.Errorf("FormatASSTime(%f) = %q; want %q", tt.input, got, tt.expected)
		}
	}
}

func TestParseTime(t *testing.T) {
	tests := []struct {
		input    string
		expected float64
	}{
		{"00:00:01,234", 1.234},
		{"01:01:01,089", 3661.089},
		{"0:00:01.23", 1.23},
		{"1:01:01.08", 3661.08},
	}

	for _, tt := range tests {
		got, err := domain.ParseTime(tt.input)
		if err != nil {
			t.Fatalf("ParseTime(%q) unexpected error: %v", tt.input, err)
		}
		if math.Abs(got-tt.expected) > 0.001 {
			t.Errorf("ParseTime(%q) = %f; want %f", tt.input, got, tt.expected)
		}
	}

	invalidTests := []string{
		"invalid",
		"00:00:aa,123",
		"00:aa:00,123",
		"aa:00:00,123",
		"00:00:00,abc",
		"00:00,123",
		"0:00:aa.12",
		"0:aa:00.12",
		"a:00:00.12",
		"0:00:00.abc",
		"0:00.12",
	}
	for _, inv := range invalidTests {
		if _, err := domain.ParseTime(inv); err == nil {
			t.Errorf("ParseTime(%q) expected error, got nil", inv)
		}
	}
}
