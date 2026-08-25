"""Per-model capability metadata from the models.dev catalog.

Reasoning effort vocabularies are MODEL-specific and discovered here — never
hardcoded. Sending an unlisted value fails upstream, so the UI offers exactly
these values (or hides the control entirely).
"""

from dataclasses import dataclass
from typing import Any, Literal

import httpx

MODELS_DEV_URL = "https://models.dev/api.json"

# translation provider preset -> models.dev provider id
PROVIDER_TO_CATALOG = {
    "openai": "openai",
    "opencode-zen": "opencode",
    "opencode-go": "opencode-go",
}


@dataclass(frozen=True)
class ReasoningSpec:
    kind: Literal["effort", "toggle", "unsupported"]
    values: tuple[str, ...] = ()


UNSUPPORTED = ReasoningSpec("unsupported", ())


class CapabilityClient:
    def __init__(self, client: httpx.Client | None = None, catalog_url: str = MODELS_DEV_URL) -> None:
        self.client = client or httpx.Client(timeout=15.0)
        self.catalog_url = catalog_url
        self._cache: dict[str, Any] | None = None

    def _catalog(self) -> dict[str, Any] | None:
        if self._cache is None:
            try:
                response = self.client.get(self.catalog_url)
                response.raise_for_status()
                self._cache = response.json()
            except Exception:  # noqa: BLE001 — any failure degrades to "unknown"
                self._cache = {}
        return self._cache or None

    def reasoning_spec(self, provider_preset: str, model_id: str) -> ReasoningSpec:
        catalog_id = PROVIDER_TO_CATALOG.get(provider_preset)
        if catalog_id is None:
            return UNSUPPORTED
        catalog = self._catalog()
        if not catalog:
            return UNSUPPORTED
        entry = catalog.get(catalog_id, {}).get("models", {}).get(model_id)
        if not entry or not entry.get("reasoning"):
            return UNSUPPORTED

        for option in entry.get("reasoning_options") or []:
            if option.get("type") == "effort" and option.get("values"):
                return ReasoningSpec("effort", tuple(str(v) for v in option["values"]))
            if option.get("type") == "toggle":
                return ReasoningSpec("toggle", ())
        return UNSUPPORTED  # reasoning=True but no usable vocabulary (e.g. nemotron)
