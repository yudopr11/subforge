import json

import httpx
import pytest

from subforge.providers.base import TranslationInput
from subforge.providers.registry import REGISTRY
from subforge.providers.translation.openai_compatible import OpenAICompatibleProvider


def chat_response(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": content}}]})


def transport_handler(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


VALID = json.dumps({"translations": [{"id": 1, "text": "Hello everyone!"}, {"id": 2, "text": "Welcome back."}]})


def test_successful_translation():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("Authorization")
        captured["body"] = json.loads(request.read())
        return chat_response(VALID)

    client = transport_handler(handler)
    provider = OpenAICompatibleProvider("http://localhost:1234/v1", "lm-studio", "qwen3-14b", client=client)
    outs = provider.translate(
        [TranslationInput(1, "Halo semuanya!"), TranslationInput(2, "Selamat datang.")], "id", "en"
    )

    assert [o.id for o in outs] == [1, 2]
    assert outs[0].text == "Hello everyone!"
    assert captured["url"] == "http://localhost:1234/v1/chat/completions"
    assert captured["auth"] == "Bearer lm-studio"
    assert captured["body"]["model"] == "qwen3-14b"
    assert '"target_language": "en"' in captured["body"]["messages"][1]["content"]


def test_strips_markdown_code_fences_from_llm_output():
    fenced = "```json\n" + VALID + "\n```"

    def handler(request):
        return chat_response(fenced)

    provider = OpenAICompatibleProvider("http://t.local/v1", "k", "m", client=transport_handler(handler))
    outs = provider.translate([TranslationInput(1, "x")], "id", "en")
    assert outs[0].text == "Hello everyone!"


def test_invalid_json_raises_value_error():
    def handler(request):
        return chat_response("not json at all")

    provider = OpenAICompatibleProvider("http://t.local/v1", "k", "m", client=transport_handler(handler))
    with pytest.raises(ValueError, match="valid JSON"):
        provider.translate([TranslationInput(1, "x")], "id", "en")


def test_http_error_propagates():
    def handler(request):
        return httpx.Response(401, json={"error": "bad key"})

    provider = OpenAICompatibleProvider("http://t.local/v1", "k", "m", client=transport_handler(handler))
    with pytest.raises(ValueError, match="HTTP 401"):
        provider.translate([TranslationInput(1, "x")], "id", "en")


def test_http_400_surfaces_server_reason():
    """PRD §21: the server's own message (unknown model, unsupported
    response_format, bad reasoning_effort, ...) reaches the user."""
    def handler(request):
        return httpx.Response(
            400,
            json={
                "error": {
                    "message": "The model 'gpt-5.6-luna' does not exist or you do not have access",
                    "type": "invalid_request_error",
                }
            },
        )

    provider = OpenAICompatibleProvider("http://t.local/v1", "k", "m", client=transport_handler(handler))
    with pytest.raises(ValueError) as exc:
        provider.translate([TranslationInput(1, "x")], "id", "en")
    error = str(exc.value)
    assert "HTTP 400" in error
    assert "does not exist" in error  # the actionable part is in the message


def test_http_400_surfaces_plain_body_when_not_json():
    def handler(request):
        return httpx.Response(400, text="model does not support response_format json_object")

    provider = OpenAICompatibleProvider("http://t.local/v1", "k", "m", client=transport_handler(handler))
    with pytest.raises(ValueError) as exc:
        provider.translate([TranslationInput(1, "x")], "id", "en")
    assert "json_object" in str(exc.value)


def test_list_models_http_error_surfaces_reason():
    def handler(request):
        return httpx.Response(500, json={"error": {"message": "rate limited"}})

    provider = OpenAICompatibleProvider("http://t.local/v1", "k", "m", client=transport_handler(handler))
    with pytest.raises(ValueError, match="HTTP 500.*rate limited"):
        provider.list_models()


def test_registered_in_registry():
    assert REGISTRY.resolve_translation("openai-compatible") is OpenAICompatibleProvider


def test_list_models_discovers_ids_for_picker():
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://x/v1/models"
        return httpx.Response(200, json={"data": [{"id": "kimi-k3"}, {"id": "glm-5.2"}]})

    provider = OpenAICompatibleProvider("http://x/v1", "k", "m", client=transport_handler(handler))
    assert provider.list_models() == ["glm-5.2", "kimi-k3"]  # sorted for stable UI ordering


def test_reasoning_only_response_raises_clear_error():
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": None}}]})

    provider = OpenAICompatibleProvider("http://t.local/v1", "k", "m", client=transport_handler(handler))
    with pytest.raises(ValueError, match="no content"):
        provider.translate([TranslationInput(1, "halo")], "id", "en")


def test_reasoning_effort_sent_only_when_provided():
    bodies = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.read()))
        return chat_response(json.dumps({"translations": [{"id": 1, "text": "ok"}]}))

    provider = OpenAICompatibleProvider("http://t.local/v1", "k", "m", client=transport_handler(handler))
    provider.translate([TranslationInput(1, "halo")], "id", "en")  # omitted
    provider.translate([TranslationInput(1, "halo")], "id", "en", reasoning_effort="max")  # sent verbatim

    assert "reasoning_effort" not in bodies[0]
    assert bodies[1]["reasoning_effort"] == "max"  # passed through untouched — UI validated it already
