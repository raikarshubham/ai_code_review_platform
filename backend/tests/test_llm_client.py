"""LLMClient against httpx.MockTransport: no network, ever."""

import json

import httpx
import pytest

from app.llm.client import LLMClient, LLMError, parse_json_object
from app.llm.config import LLMSettings

SETTINGS = LLMSettings(provider="gemini", base_url="https://llm.test/v1beta/openai", model="m", api_key="secret")


def reply(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": content}}]})


def client_with(handler) -> LLMClient:
    return LLMClient(SETTINGS, transport=httpx.MockTransport(handler))


def test_request_shape_and_parsed_reply():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return reply('{"findings": []}')

    result = client_with(handler).chat_json([{"role": "user", "content": "hi"}])

    assert result == {"findings": []}
    assert seen["url"] == "https://llm.test/v1beta/openai/chat/completions"
    assert seen["auth"] == "Bearer secret"
    assert seen["body"]["model"] == "m"
    assert seen["body"]["temperature"] == 0
    assert seen["body"]["response_format"] == {"type": "json_object"}


@pytest.mark.parametrize("content", ['```json\n{"a": 1}\n```', '```\n{"a": 1}\n```', '  {"a": 1}  '])
def test_code_fences_are_stripped(content):
    assert parse_json_object(content) == {"a": 1}


@pytest.mark.parametrize("content", ["not json", "[1, 2]", "", None])
def test_unusable_replies_raise(content):
    with pytest.raises(LLMError):
        parse_json_object(content)


@pytest.mark.parametrize("status", [400, 429, 500])
def test_http_errors_raise_without_leaking_the_key(status):
    with pytest.raises(LLMError, match=str(status)) as caught:
        client_with(lambda request: httpx.Response(status, text="nope")).chat_json([])
    assert "secret" not in str(caught.value)


@pytest.mark.parametrize("body", [
    {"error": {"message": "Please pass a valid API key"}},  # OpenAI / Groq shape
    [{"error": {"code": 400, "message": "Please pass a valid API key"}}],  # Gemini shape
])
def test_http_error_shows_the_providers_message(body):
    with pytest.raises(LLMError) as caught:
        client_with(lambda request: httpx.Response(400, json=body)).chat_json([])
    assert str(caught.value) == "gemini returned HTTP 400: Please pass a valid API key"


def test_timeout_raises():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(LLMError, match="timed out"):
        client_with(handler).chat_json([])


def test_unexpected_response_shape_raises():
    with pytest.raises(LLMError, match="shape"):
        client_with(lambda request: httpx.Response(200, json={"error": "x"})).chat_json([])
