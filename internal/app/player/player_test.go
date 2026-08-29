package player_test

import (
	"strings"
	"testing"

	"github.com/yudopr11/subforge/internal/app/player"
)

func TestBuildPlayerCommand(t *testing.T) {
	tests := []struct {
		name       string
		playerBin  string
		audioPath  string
		start      float64
		duration   float64
		wantBinary string
		contains   []string
	}{
		{
			name:       "ffplay command",
			playerBin:  "/usr/bin/ffplay",
			audioPath:  "/tmp/test.wav",
			start:      1.5,
			duration:   3.0,
			wantBinary: "/usr/bin/ffplay",
			contains:   []string{"-nodisp", "-autoexit", "-loglevel", "quiet", "-ss", "1.500", "-t", "3.000", "/tmp/test.wav"},
		},
		{
			name:       "mpv command",
			playerBin:  "mpv",
			audioPath:  "/tmp/test.wav",
			start:      2.0,
			duration:   4.5,
			wantBinary: "mpv",
			contains:   []string{"--really-quiet", "--no-video", "--start=2.000", "--length=4.500", "/tmp/test.wav"},
		},
		{
			name:       "cvlc command",
			playerBin:  "/usr/local/bin/cvlc",
			audioPath:  "/tmp/test.wav",
			start:      1.0,
			duration:   2.0,
			wantBinary: "/usr/local/bin/cvlc",
			contains:   []string{"--intf", "dummy", "--play-and-exit", "--start-time=1.000", "--stop-time=3.000", "/tmp/test.wav"},
		},
		{
			name:       "powershell fallback",
			playerBin:  "powershell",
			audioPath:  `C:\audio.wav`,
			start:      1.0,
			duration:   2.0,
			wantBinary: "powershell",
			contains:   []string{"-NoProfile", "-NonInteractive", "-Command", "SoundPlayer"},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			bin, args := player.BuildPlayerCommand(tt.playerBin, tt.audioPath, tt.start, tt.duration)
			if bin != tt.wantBinary {
				t.Errorf("BuildPlayerCommand() bin = %q; want %q", bin, tt.wantBinary)
			}
			argStr := strings.Join(args, " ")
			for _, exp := range tt.contains {
				if !strings.Contains(argStr, exp) {
					t.Errorf("BuildPlayerCommand() args %q does not contain expected snippet %q", argStr, exp)
				}
			}
		})
	}
}

func TestSegmentPlayerStopWithoutPlay(t *testing.T) {
	p := player.NewSegmentPlayer("/tmp/audio.wav")
	msg := p.Stop()
	if !strings.Contains(msg, "Stopped") {
		t.Errorf("Stop() = %q; want to contain 'Stopped'", msg)
	}
}
