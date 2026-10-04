"""LLMClient against httpx.MockTransport: no network, ever."""

import json

import httpx
import pytest

from app.llm.client import LLMClient, LLMError, parse_json_object
from app.llm.config import LLMSettings

SETTINGS = LLMSettings(provider="gemini", base_url="https://llm.test/v1beta/openai", model="m", api_key="secret")


def reply(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": content}}]})


class FakeTime:
    """Stands in for time.sleep and time.monotonic: sleeping just moves the clock forward."""

    def __init__(self):
        self.now = 0.0
        self.waits: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.waits.append(seconds)
        self.now += seconds


def client_with(handler, fake_time: FakeTime | None = None) -> LLMClient:
    fake_time = fake_time or FakeTime()
    return LLMClient(SETTINGS, transport=httpx.MockTransport(handler), sleep=fake_time.sleep, clock=fake_time.clock)


def scripted(*responses):
    """A handler that returns the given responses in order and counts the requests."""
    queue = list(responses)

    def handler(request):
        handler.calls += 1
        response = queue.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    handler.calls = 0
    return handler


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


# --- Retries --------------------------------------------------------------------------------

OK = reply('{"ok": true}')


def overloaded():
    return httpx.Response(503, json=[{"error": {"message": "high demand"}}])


def test_503_is_retried_with_exponential_backoff():
    time_ = FakeTime()
    handler = scripted(overloaded(), overloaded(), OK)
    assert client_with(handler, time_).chat_json([]) == {"ok": True}
    assert (handler.calls, time_.waits) == (3, [2, 4])


def test_gives_up_after_three_attempts():
    handler = scripted(overloaded(), overloaded(), overloaded())
    with pytest.raises(LLMError, match=r"503: high demand \(gave up after 3 attempts\)"):
        client_with(handler).chat_json([])
    assert handler.calls == 3


def test_429_waits_as_long_as_retry_after_says():
    time_ = FakeTime()
    handler = scripted(httpx.Response(429, headers={"Retry-After": "3"}, text="slow down"), OK)
    client_with(handler, time_).chat_json([])
    assert time_.waits == [3]


def test_429_uses_geminis_retry_delay_from_the_body():
    body = [{"error": {"code": 429, "message": "quota", "details": [
        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "7s"}]}}]
    time_ = FakeTime()
    client_with(scripted(httpx.Response(429, json=body), OK), time_).chat_json([])
    assert time_.waits == [7]


def test_long_retry_after_fails_now_instead_of_waiting():
    time_ = FakeTime()
    handler = scripted(httpx.Response(429, headers={"Retry-After": "45"}))
    with pytest.raises(LLMError, match="rate limited; retry in 45 s"):
        client_with(handler, time_).chat_json([])
    assert time_.waits == []


def test_daily_quota_wait_is_shown_in_hours():
    # Seen live: Gemini's free tier ran out for the day and asked for a 20538 s wait.
    handler = scripted(httpx.Response(429, headers={"Retry-After": "20538"}))
    with pytest.raises(LLMError, match=r"retry in 5 h 42 min \(daily quota likely used up\)"):
        client_with(handler).chat_json([])


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_client_errors_are_not_retried(status):
    handler = scripted(httpx.Response(status, text="no"), OK)
    with pytest.raises(LLMError, match=str(status)):
        client_with(handler).chat_json([])
    assert handler.calls == 1


def test_invalid_json_is_retried_once():
    handler = scripted(reply("not json"), OK)
    assert client_with(handler).chat_json([]) == {"ok": True}
    handler = scripted(reply("not json"), reply("still not"), OK)
    with pytest.raises(LLMError, match="not valid JSON"):
        client_with(handler).chat_json([])
    assert handler.calls == 2


def test_timeout_is_not_retried():
    request = httpx.Request("POST", "https://llm.test")
    handler = scripted(httpx.ReadTimeout("slow", request=request), OK)
    with pytest.raises(LLMError, match="timed out"):
        client_with(handler).chat_json([])
    assert handler.calls == 1


def test_connection_errors_are_retried():
    request = httpx.Request("POST", "https://llm.test")
    handler = scripted(httpx.ConnectError("refused", request=request), OK)
    assert client_with(handler).chat_json([]) == {"ok": True}


def test_deadline_stops_further_retries():
    time_ = FakeTime()

    def slow_overloaded(request):
        time_.now += 59  # each attempt takes 59 s of the 120 s budget
        return overloaded()

    with pytest.raises(LLMError, match="gave up after 2 attempts"):
        client_with(slow_overloaded, time_).chat_json([])
    assert time_.waits == [2]  # 59 + 2 + 59 = 120: no time left for a third try
