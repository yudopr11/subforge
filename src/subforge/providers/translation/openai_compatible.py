"""OpenAI-compatible translation provider (LM Studio, Ollama, OpenAI, ... — ARCH §14)."""

import json
import re

import httpx

from subforge.providers.base import TranslationInput, TranslationOutput
from subforge.providers.registry import REGISTRY

_SYSTEM_PROMPT = (
    "You are a professional subtitle translator. "
    "Translate each numbered subtitle segment from {source} to {target}. "
    "Preserve meaning, tone, and terminology. Keep translations concise like natural subtitles. "
    "Respond ONLY with valid JSON of the form: "
    '{{"translations": [{{"id": <int>, "text": "<string>"}}]}} '
    "with exactly one entry per input id. Never modify ids."
)


class OpenAICompatibleProvider:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.client = client or httpx.Client(timeout=120.0)
        # Auto-detected: newer OpenAI reasoning models reject max_tokens and
        # demand max_completion_tokens (ARCH §14). None = not probed yet.
        self._use_max_completion_tokens: bool | None = None

    def translate(
        self,
        segments: list[TranslationInput],
        source_language: str,
        target_language: str,
        reasoning_effort: str | None = None,
    ) -> list[TranslationOutput]:
        payload_extra: dict[str, str] = {}
        if reasoning_effort is not None:
            # Value comes from Task 21 capability discovery; sent verbatim or not at all.
            payload_extra["reasoning_effort"] = reasoning_effort
        payload = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "max_tokens": 2048,
            "messages": [
                {
                    "role": "system",
                    "content": _SYSTEM_PROMPT.format(source=source_language, target=target_language),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "source_language": source_language,
                            "target_language": target_language,
                            "segments": [{"id": s.id, "text": s.text} for s in segments],
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            **payload_extra,
        }
        response = self._chat_completions(payload)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            # PRD §21: fail loudly with the server's own reason (e.g. unknown
            # model, model doesn't support json_object, bad reasoning_effort).
            raise ValueError(
                f"translation request failed (HTTP {exc.response.status_code}): "
                f"{_error_detail(exc.response)}"
            ) from exc

        choice = response.json()["choices"][0]["message"]
        content = choice.get("content")
        if content is None:
            # Reasoning models (MiMo, Nemotron, ...) sometimes answer with reasoning
            # fields only. Fail loudly here; batch validation is NOT the right place.
            raise ValueError(
                "translation model returned no content (reasoning-only response); "
                "pick a chat-completions-capable model"
            )
        return self._parse(content)

    def _chat_completions(self, payload: dict[str, object]) -> httpx.Response:
        """POST /chat/completions with a one-shot token-parameter fallback.

        Newer OpenAI reasoning models reject ``max_tokens`` and demand
        ``max_completion_tokens``; LM Studio / Ollama and older models expect the
        former. We can't know without probing, so when the server's error says so
        we retry ONCE with the other parameter and remember the preference for
        the rest of this provider session — later batches skip the rejected call.
        """
        if self._use_max_completion_tokens:
            payload = dict(payload)
            payload["max_completion_tokens"] = payload.pop("max_tokens")
        response = self.client.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        if (
            self._use_max_completion_tokens is not True
            and response.status_code == 400
            and _wants_max_completion_tokens(response)
        ):
            self._use_max_completion_tokens = True
            payload = dict(payload)
            payload["max_completion_tokens"] = payload.pop("max_tokens")
            response = self.client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
        return response

    def list_models(self) -> list[str]:
        """Fetch available model IDs from GET /models — live discovery for the TUI picker."""
        response = self.client.get(
            f"{self.base_url}/models",
            headers={"Authorization": f"Bearer {self.api_key}"},
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ValueError(
                f"model discovery failed (HTTP {exc.response.status_code}): "
                f"{_error_detail(exc.response)}"
            ) from exc
        return sorted(str(item["id"]) for item in response.json().get("data", []) if item.get("id"))

    @staticmethod
    def _parse(content: str) -> list[TranslationOutput]:
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"translation provider did not return valid JSON: {exc}") from exc
        return [TranslationOutput(id=item["id"], text=str(item["text"])) for item in data["translations"]]


def _wants_max_completion_tokens(response: httpx.Response) -> bool:
    """True when the server rejected ``max_tokens`` and asked for the other name.

    Matches OpenAI-style messages like ``Unsupported parameter: 'max_tokens' is
    not supported with this model. Use 'max_completion_tokens' instead.``
    """
    message = response.text or ""
    try:
        payload = response.json()
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict) and error.get("message"):
                message = str(error["message"])
    except ValueError:
        pass
    lowered = message.lower()
    return "max_tokens" in lowered and "max_completion_tokens" in lowered


def _error_detail(response: httpx.Response) -> str:
    """Best human-readable reason from an HTTP error response body."""
    try:
        payload = response.json()
    except ValueError:
        payload = None
    message = None
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            message = error.get("message")
    detail = message or response.text or "(empty response body)"
    return str(detail).strip()[:400]


REGISTRY.register_translation("openai-compatible", OpenAICompatibleProvider)
