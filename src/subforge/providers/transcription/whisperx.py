"""Local WhisperX provider. whisperx is an OPTIONAL dependency (ARCH §7, §27)."""

import gc
from pathlib import Path

from subforge.models.transcript import Transcript, TranscriptSegment
from subforge.providers.registry import REGISTRY


class WhisperXProvider:
    def __init__(self, model: str = "large-v3", device: str = "auto", compute_type: str = "auto") -> None:
        self.model_name = model
        self.device = device
        self.compute_type = compute_type

    def transcribe(self, audio_path: Path, language: str | None = None) -> Transcript:
        try:
            import whisperx  # noqa: PLC0415 — heavy optional import, deferred on purpose
        except ImportError as exc:
            raise RuntimeError(
                "WhisperX is not installed. Install local transcription support with: "
                'pip install "subforge[local]"  (or configure TRANSCRIPTION_PROVIDER=remote)'
            ) from exc

        device = self.device if self.device != "auto" else "cpu"
        compute_type = self.compute_type if self.compute_type != "auto" else "int8"
        model = whisperx.load_model(self.model_name, device=device, compute_type=compute_type)
        audio = whisperx.load_audio(str(audio_path))
        try:
            result = model.transcribe(audio, batch_size=8, language=language)
        finally:
            del model
            gc.collect()

        segments = [
            TranscriptSegment(
                id=int(i),
                start=float(s["start"]),
                end=float(s["end"]),
                text=str(s["text"]).strip(),
            )
            for i, s in enumerate(result.get("segments", []))
        ]
        return Transcript(language=result.get("language", language), segments=segments)


REGISTRY.register_transcription("local-whisperx", WhisperXProvider)
