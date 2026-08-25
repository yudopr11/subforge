import json

import httpx

from subforge.providers.capabilities import CapabilityClient, ReasoningSpec

CATALOG = {
    "openai": {
        "models": {
            "gpt-5.6-luna": {
                "reasoning": True,
                "reasoning_options": [{"type": "effort", "values": ["none", "low", "medium", "high"]}],
            },
            "gpt-4o": {"reasoning": False},
        }
    },
    "opencode": {
        "models": {
            "glm-5.2": {"reasoning": True, "reasoning_options": [{"type": "effort", "values": ["high", "max"]}]},
            "kimi-k3": {"reasoning": True, "reasoning_options": [{"type": "effort", "values": ["max"]}]},
            "nemotron-3-ultra-free": {"reasoning": True, "reasoning_options": []},
            "qwen3-coder": {"reasoning": False},
            "longcat-2.0": {"reasoning": True, "reasoning_options": [{"type": "toggle"}]},
        }
    },
    "opencode-go": {
        "models": {
            "grok-4.5": {
                "reasoning": True,
                "reasoning_options": [{"type": "effort", "values": ["low", "medium", "high"]}],
            },
        }
    },
}


def make_client() -> CapabilityClient:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://models.dev/api.json"
        return httpx.Response(200, text=json.dumps(CATALOG))

    return CapabilityClient(client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_effort_values_come_verbatim_from_metadata():
    c = make_client()
    assert c.reasoning_spec("opencode-zen", "glm-5.2") == ReasoningSpec("effort", ("high", "max"))
    assert c.reasoning_spec("opencode-zen", "kimi-k3") == ReasoningSpec("effort", ("max",))
    assert c.reasoning_spec("opencode-go", "grok-4.5") == ReasoningSpec("effort", ("low", "medium", "high"))


def test_non_reasoning_model_is_unsupported():
    c = make_client()
    assert c.reasoning_spec("openai", "gpt-4o") == ReasoningSpec("unsupported", ())
    assert c.reasoning_spec("opencode-zen", "qwen3-coder") == ReasoningSpec("unsupported", ())


def test_toggle_is_its_own_kind():
    c = make_client()
    assert c.reasoning_spec("opencode-zen", "longcat-2.0").kind == "toggle"


def test_reasoning_true_with_no_options_is_unsupported():
    # nemotron advertises reasoning but exposes no effort vocabulary -> hide control
    c = make_client()
    assert c.reasoning_spec("opencode-zen", "nemotron-3-ultra-free") == ReasoningSpec("unsupported", ())


def test_unknown_model_or_local_provider_is_unsupported():
    c = make_client()
    assert c.reasoning_spec("opencode-zen", "totally-unknown").kind == "unsupported"
    assert c.reasoning_spec("openai-compatible", "qwen3-14b").kind == "unsupported"  # local server


def test_catalog_fetch_failure_is_unsupported_not_crash():
    def handler(request):
        return httpx.Response(503)

    c = CapabilityClient(client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert c.reasoning_spec("openai", "gpt-4o").kind == "unsupported"
