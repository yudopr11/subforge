"""Generate a deterministic 1-second sine-wave WAV fixture at test time.

Binary audio is never committed (ARCH §29/§34); run this to produce
tests/fixtures/sine_1s.wav locally when a real decodable file is needed.
"""

import math
import struct
import wave
from pathlib import Path

RATE = 16_000
FREQ = 440.0
SECONDS = 1


def make_sine_wav(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(RATE)
        frames = b"".join(
            struct.pack("<h", int(0.5 * 32767 * math.sin(2 * math.pi * FREQ * i / RATE)))
            for i in range(RATE * SECONDS)
        )
        wf.writeframes(frames)
    return path


if __name__ == "__main__":
    print(make_sine_wav(Path(__file__).parent / "sine_1s.wav"))
