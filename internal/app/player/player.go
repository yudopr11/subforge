package player

import (
	"fmt"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"sync"

	"github.com/yudopr11/subforge/internal/app/binaries"
)

type SegmentPlayer struct {
	audioPath  string
	playerName string
	currentCmd *exec.Cmd
	mu         sync.Mutex
}

func DetectAudioPlayer() string {
	candidates := []string{"ffplay", "mpv", "cvlc"}
	for _, name := range candidates {
		if path, err := binaries.FindBinary(name); err == nil {
			return path
		}
	}
	if runtime.GOOS == "windows" {
		// Try wmplayer (Windows Media Player), then fall back to PowerShell SoundPlayer
		if path, err := binaries.FindBinary("wmplayer"); err == nil {
			return path
		}
		return "powershell"
	}
	return ""
}

func BuildPlayerCommand(playerBin, audioPath string, start, duration float64) (string, []string) {
	base := strings.ToLower(filepath.Base(playerBin))

	switch {
	case strings.Contains(base, "ffplay"):
		return playerBin, []string{
			"-nodisp", "-autoexit", "-loglevel", "quiet",
			"-ss", fmt.Sprintf("%.3f", start),
			"-t", fmt.Sprintf("%.3f", duration),
			audioPath,
		}
	case strings.Contains(base, "mpv"):
		return playerBin, []string{
			"--really-quiet", "--no-video",
			fmt.Sprintf("--start=%.3f", start),
			fmt.Sprintf("--length=%.3f", duration),
			audioPath,
		}
	case strings.Contains(base, "cvlc"):
		return playerBin, []string{
			"--intf", "dummy", "--play-and-exit",
			fmt.Sprintf("--start-time=%.3f", start),
			fmt.Sprintf("--stop-time=%.3f", start+duration),
			audioPath,
		}
	case strings.Contains(base, "wmplayer"):
		// Windows Media Player: no native seek-to flag, play full file from position 0.
		// Best-effort: just play the segment file directly.
		return playerBin, []string{audioPath, "/play", "/close"}
	case strings.Contains(base, "powershell"):
		// Use Windows built-in SoundPlayer for WAV, or mciSendString for general audio.
		// mciSendString supports seek + duration and works on all Windows without WPF.
		absPath := strings.ReplaceAll(audioPath, `\`, `\\`)
		startMs := int(start * 1000)
		endMs := int((start + duration) * 1000)
		psScript := fmt.Sprintf(
			`$sig = '[DllImport(\"winmm.dll\")]public static extern int mciSendString(string cmd,System.Text.StringBuilder ret,int retLen,System.IntPtr hwnd);';`+
				`$t = Add-Type -MemberDefinition $sig -Name 'MCI' -Namespace 'Win32' -PassThru;`+
				`$null = $t::mciSendString('open \"%s\" type mpegvideo alias seg','',0,[System.IntPtr]::Zero);`+
				`$null = $t::mciSendString('play seg from %d to %d','',0,[System.IntPtr]::Zero);`+
				`Start-Sleep -Milliseconds %d;`+
				`$null = $t::mciSendString('close seg','',0,[System.IntPtr]::Zero)`,
			absPath, startMs, endMs, endMs-startMs+200,
		)
		return playerBin, []string{"-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", psScript}
	default:
		return playerBin, []string{audioPath}
	}
}

func NewSegmentPlayer(audioPath string) *SegmentPlayer {
	return &SegmentPlayer{
		audioPath:  audioPath,
		playerName: DetectAudioPlayer(),
	}
}

func (p *SegmentPlayer) PlaySegment(start, end float64) (string, error) {
	p.mu.Lock()
	defer p.mu.Unlock()

	p.stopLocked()

	if p.playerName == "" {
		return "", fmt.Errorf("no audio player found (install ffplay or mpv)")
	}

	duration := end - start
	if duration <= 0 {
		duration = 0.5
	}

	bin, args := BuildPlayerCommand(p.playerName, p.audioPath, start, duration)
	cmd := exec.Command(bin, args...)
	if err := cmd.Start(); err != nil {
		return "", fmt.Errorf("failed to start audio playback: %w", err)
	}
	p.currentCmd = cmd

	go func() {
		_ = cmd.Wait()
		p.mu.Lock()
		if p.currentCmd == cmd {
			p.currentCmd = nil
		}
		p.mu.Unlock()
	}()

	return fmt.Sprintf("▶ Playing %.2fs → %.2fs", start, end), nil
}

func (p *SegmentPlayer) Stop() string {
	p.mu.Lock()
	defer p.mu.Unlock()
	p.stopLocked()
	return "■ Stopped"
}

func (p *SegmentPlayer) stopLocked() {
	if p.currentCmd != nil && p.currentCmd.Process != nil {
		_ = p.currentCmd.Process.Kill()
		p.currentCmd = nil
	}
}
