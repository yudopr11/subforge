package pipeline

import (
	"fmt"
	"os"
	"os/exec"

	"github.com/yudopr11/subforge/internal/app/binaries"
)

func Prepare16kHzAudio(inputPath, outputWav string) error {
	if fi, err := os.Stat(outputWav); err == nil && fi.Size() > 44 {
		return nil // Already prepared
	}

	ffmpegBin, err := binaries.FindBinary("ffmpeg")
	if err != nil {
		return fmt.Errorf("ffmpeg not found (required for audio conversion): %w", err)
	}

	cmd := exec.Command(
		ffmpegBin,
		"-y",
		"-i", inputPath,
		"-ar", "16000",
		"-ac", "1",
		"-c:a", "pcm_s16le",
		outputWav,
		"-loglevel", "error",
	)

	if out, err := cmd.CombinedOutput(); err != nil {
		return fmt.Errorf("ffmpeg audio conversion failed: %s (%w)", string(out), err)
	}
	return nil
}
