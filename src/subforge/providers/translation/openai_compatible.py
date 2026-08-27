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
    "with exactly one entry per input id. Never modify ids. "
    "Do not include any conversational commentary or extra keys."
)


NON_CHAT_KEYWORDS = (
    "embed",
    "embedding",
    "nomic-embed",
    "bge-",
    "bert-",
    "minilm",
    "rerank",
    "whisper",
)

LOCAL_SERVER_CANDIDATES = [
    "http://localhost:1234/v1",
    "http://localhost:11434/v1",
    "http://127.0.0.1:1234/v1",
    "http://127.0.0.1:11434/v1",
]


def is_chat_model(model_id: str) -> bool:
    """True if model ID looks like a generative LLM rather than an embedding model."""
    lowered = model_id.lower()
    return not any(kw in lowered for kw in NON_CHAT_KEYWORDS)


def detect_local_server(
    client: httpx.Client | None = None,
    candidates: list[str] | None = None,
) -> tuple[str, list[str]] | None:
    """Probe running local LLM endpoints (LM Studio, Ollama). Returns (base_url, chat_models)."""
    http_client = client or httpx.Client(timeout=2.0)
    urls = candidates or LOCAL_SERVER_CANDIDATES
    for url in urls:
        try:
            prov = OpenAICompatibleProvider(base_url=url, api_key="", model="discovery", client=http_client)
            models = prov.list_models()
            if models:
                return url, models
        except Exception:  # noqa: BLE001, S112
            continue
    return None


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

    def _auth_headers(self) -> dict[str, str]:
        if self.api_key:
            return {"Authorization": f"Bearer {self.api_key}"}
        return {}

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
            "max_tokens": 8192,
            "temperature": 0.1,
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

        choice_obj = response.json()["choices"][0]
        choice = choice_obj["message"]
        content = choice.get("content")
        finish_reason = choice_obj.get("finish_reason")

        if content is None or not content.strip():
            if finish_reason == "length":
                raise ValueError(
                    "translation model ran out of tokens (finish_reason='length'); "
                    "increase token limit or pick a faster model"
                )
            reasoning = choice.get("reasoning_content") or choice.get("reasoning") or ""
            if reasoning:
                try:
                    return self._parse(reasoning)
                except Exception:  # noqa: BLE001, S110
                    pass
            raise ValueError(
                "translation model returned no content; pick a chat-completions-capable model"
            )
        return self._parse(content)

    def _chat_completions(self, payload: dict[str, object]) -> httpx.Response:
        """POST /chat/completions with token-parameter and response-format fallbacks.

        Newer OpenAI reasoning models reject ``max_tokens`` and demand
        ``max_completion_tokens``; LM Studio / Ollama and older models expect the
        former. We probe and remember the preference for the rest of this session.
        """
        headers = self._auth_headers()
        current_payload = dict(payload)
        if self._use_max_completion_tokens:
            current_payload["max_completion_tokens"] = current_payload.pop("max_tokens", 8192)

        response = self.client.post(
            f"{self.base_url}/chat/completions",
            json=current_payload,
            headers=headers,
        )

        # Fallback 1: max_tokens -> max_completion_tokens
        if (
            self._use_max_completion_tokens is not True
            and response.status_code == 400
            and _wants_max_completion_tokens(response)
        ):
            self._use_max_completion_tokens = True
            current_payload["max_completion_tokens"] = current_payload.pop("max_tokens", 8192)
            response = self.client.post(
                f"{self.base_url}/chat/completions",
                json=current_payload,
                headers=headers,
            )

        # Fallback 2: response_format not supported
        if response.status_code == 400 and "response_format" in current_payload:
            err_msg = _error_detail(response).lower()
            if "response_format" in err_msg or "json_object" in err_msg or "schema" in err_msg:
                current_payload.pop("response_format", None)
                response = self.client.post(
                    f"{self.base_url}/chat/completions",
                    json=current_payload,
                    headers=headers,
                )

        return response

    def list_models(self) -> list[str]:
        """Fetch available model IDs from GET /models — live discovery for the TUI picker."""
        response = self.client.get(
            f"{self.base_url}/models",
            headers=self._auth_headers(),
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ValueError(
                f"model discovery failed (HTTP {exc.response.status_code}): "
                f"{_error_detail(exc.response)}"
            ) from exc
        raw_ids = [str(item["id"]) for item in response.json().get("data", []) if item.get("id")]
        filtered = [mid for mid in raw_ids if is_chat_model(mid)]
        return sorted(filtered if filtered else raw_ids)

    @staticmethod
    def _parse(content: str) -> list[TranslationOutput]:
        text = content.strip()
        # Remove markdown code fences if wrapped
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            text = text.strip()

        # Attempt direct JSON decode first
        data = None
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Look for outermost JSON object {...} or array [...]
            match = re.search(r"(\{.*\}|\[.*\])", text, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                except json.JSONDecodeError:
                    pass

        if data is None:
            # Fallback for partial/truncated JSON or embedded objects:
            # Match individual {"id": 1, "text": "..."} blocks
            obj_matches = re.findall(r'\{\s*"id"\s*:\s*(\d+)\s*,\s*"text"\s*:\s*"((?:\\.|[^"\\])*)"\s*\}', text)
            if obj_matches:
                return [
                    TranslationOutput(id=int(m[0]), text=json.loads(f'"{m[1]}"'))
                    for m in obj_matches
                ]
            raise ValueError(f"translation provider did not return valid JSON: {content[:100]}")

        # Extract items
        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            if "translations" in data and isinstance(data["translations"], list):
                items = data["translations"]
            elif "segments" in data and isinstance(data["segments"], list):
                items = data["segments"]
            else:
                for k, v in data.items():
                    if isinstance(v, dict) and "text" in v:
                        item_id = v.get("id", k)
                        items.append({"id": item_id, "text": v["text"]})
                    elif str(k).isdigit() or (isinstance(k, str) and k.strip().isdigit()):
                        items.append({"id": int(k), "text": str(v)})

        if not items:
            raise ValueError("translation JSON missing 'translations' list")

        return [TranslationOutput(id=int(item["id"]), text=str(item["text"])) for item in items]


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
