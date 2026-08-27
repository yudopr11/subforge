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
        return httpx.Response(400, text="model does not support prompt feature XYZ")

    provider = OpenAICompatibleProvider("http://t.local/v1", "k", "m", client=transport_handler(handler))
    with pytest.raises(ValueError) as exc:
        provider.translate([TranslationInput(1, "x")], "id", "en")
    assert "XYZ" in str(exc.value)


def test_empty_api_key_omits_authorization_header():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("Authorization")
        return chat_response(VALID)

    provider = OpenAICompatibleProvider("http://localhost:1234/v1", "", "qwen", client=transport_handler(handler))
    provider.translate([TranslationInput(1, "x")], "id", "en")
    assert captured["auth"] is None


def test_response_format_unsupported_retries_without_response_format():
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.read())
        bodies.append(body)
        if len(bodies) == 1:
            return httpx.Response(400, json={"error": {"message": "response_format json_object is not supported"}})
        return chat_response(VALID)

    provider = OpenAICompatibleProvider("http://localhost:1234/v1", "", "local-model", client=transport_handler(handler))
    outs = provider.translate([TranslationInput(1, "x")], "id", "en")
    assert len(outs) == 2
    assert "response_format" in bodies[0]
    assert "response_format" not in bodies[1]


def test_extracts_json_from_conversational_preambles_and_varied_formats():
    conversational = (
        "Sure, here is your subtitle translation:\n\n"
        "```json\n"
        '{"segments": [{"id": 1, "text": "Halo dunia"}]}\n'
        "```\n"
        "I hope this helps your video!"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return chat_response(conversational)

    provider = OpenAICompatibleProvider("http://localhost:1234/v1", "", "local-model", client=transport_handler(handler))
    outs = provider.translate([TranslationInput(1, "Hello world")], "en", "id")
    assert len(outs) == 1
    assert outs[0].id == 1
    assert outs[0].text == "Halo dunia"


def test_max_tokens_400_retries_with_max_completion_tokens():
    """Newer reasoning models reject max_tokens: auto-fallback once, remember."""
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.read()))
        if len(bodies) == 1:
            return httpx.Response(
                400,
                json={
                    "error": {
                        "message": "Unsupported parameter: 'max_tokens' is not supported with this model. "
                        "Use 'max_completion_tokens' instead."
                    }
                },
            )
        return chat_response(VALID)

    provider = OpenAICompatibleProvider("http://t.local/v1", "k", "m", client=transport_handler(handler))
    outs = provider.translate([TranslationInput(1, "x")], "id", "en")

    assert [o.id for o in outs] == [1, 2]
    assert "max_tokens" in bodies[0]
    assert bodies[1]["max_completion_tokens"] == 8192
    assert "max_tokens" not in bodies[1]
    assert provider._use_max_completion_tokens is True


def test_max_completion_tokens_preference_skips_rejected_call():
    """Later batches go straight to max_completion_tokens — no wasted 400."""
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.read()))
        return chat_response(VALID)

    provider = OpenAICompatibleProvider("http://t.local/v1", "k", "m", client=transport_handler(handler))
    provider._use_max_completion_tokens = True
    provider.translate([TranslationInput(1, "x")], "id", "en")
    provider.translate([TranslationInput(1, "x")], "id", "en")

    assert len(bodies) == 2  # no 400 probe at all
    assert all("max_completion_tokens" in b and "max_tokens" not in b for b in bodies)


def test_unrelated_400_is_not_retried():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(400, json={"error": {"message": "context length exceeded"}})

    provider = OpenAICompatibleProvider("http://t.local/v1", "k", "m", client=transport_handler(handler))
    with pytest.raises(ValueError, match="context length exceeded"):
        provider.translate([TranslationInput(1, "x")], "id", "en")
    assert len(calls) == 1  # only the original call; error body surfaced
    assert provider._use_max_completion_tokens is None


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


def test_is_chat_model_filters_embedding_models():
    from subforge.providers.translation.openai_compatible import is_chat_model

    assert is_chat_model("prism-ml/bonsai-27b") is True
    assert is_chat_model("qwen2.5-coder-7b-instruct") is True
    assert is_chat_model("text-embedding-nomic-embed-text-v1.5") is False
    assert is_chat_model("bge-large-en-v1.5") is False
    assert is_chat_model("whisper-large-v3") is False


def test_list_models_filters_out_embeddings():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "text-embedding-nomic-embed-text-v1.5"},
                    {"id": "prism-ml/bonsai-27b"},
                    {"id": "bge-reranker-v2-m3"},
                ]
            },
        )

    provider = OpenAICompatibleProvider("http://localhost:1234/v1", "", "discovery", client=transport_handler(handler))
    assert provider.list_models() == ["prism-ml/bonsai-27b"]


def test_detect_local_server_probes_candidates():
    from subforge.providers.translation.openai_compatible import detect_local_server

    def handler(request: httpx.Request) -> httpx.Response:
        if "1234" in str(request.url):
            return httpx.Response(200, json={"data": [{"id": "prism-ml/bonsai-27b"}]})
        return httpx.Response(500)

    client = transport_handler(handler)
    res = detect_local_server(client=client, candidates=["http://localhost:1234/v1", "http://localhost:11434/v1"])
    assert res is not None
    assert res[0] == "http://localhost:1234/v1"
    assert res[1] == ["prism-ml/bonsai-27b"]

