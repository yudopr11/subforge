"""Cloud provider preset URLs. The ONLY place these live (AGENTS.md, ARCH §28).

User keys/models never live here — they belong to AppConfig
(~/.config/subforge/config.json).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderPreset:
    name: str
    base_url: str


TRANSLATION_PRESETS: dict[str, ProviderPreset] = {
    "openai": ProviderPreset(name="OpenAI", base_url="https://api.openai.com/v1"),
    "opencode-zen": ProviderPreset(name="OpenCode Zen", base_url="https://opencode.ai/zen/v1"),
    "opencode-go": ProviderPreset(name="OpenCode Go", base_url="https://opencode.ai/zen/go/v1"),
}

OPENAI_TRANSCRIPTION_BASE_URL = "https://api.openai.com/v1"
