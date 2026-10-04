"""Minimal OpenAI-compatible chat client that asks for, and returns, a JSON object.

We call the HTTP API directly with httpx instead of using a provider SDK: one small client
covers Gemini, Groq and Ollama, and tests can swap the network for httpx.MockTransport.

Free tiers fail in predictable ways, so chat_json retries the ones a retry can fix:
    429 rate limited     -> wait as long as the server says (Retry-After), then retry
    500/502/503/504      -> exponential backoff (2 s, 4 s), then retry ("high demand" is a 503)
    connection failure   -> backoff and retry
    reply isn't JSON     -> retry once right away (CLAUDE.md)
    400/401/403/404      -> no retry: the request itself is wrong (bad key, retired model)
    timeout              -> no retry: it already took the full timeout, retrying doubles that
Everything happens inside one deadline, so a request can never hang for minutes.
"""

import json
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx

from app.llm.config import LLMSettings

TIMEOUT_SECONDS = 60  # one attempt
DEADLINE_SECONDS = 120  # all attempts and waits together
MAX_ATTEMPTS = 3
BACKOFF_SECONDS = 2  # first wait; doubles each retry
MAX_WAIT_SECONDS = 30  # a longer Retry-After fails now instead of holding the HTTP request open
RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class LLMError(Exception):
    """The LLM call failed or returned something unusable. The pipeline turns this into
    `ai_review.error` and still returns the static results."""

    def __init__(self, message: str, *, status: int | None = None, retryable: bool = False,
                 retry_after: float | None = None, invalid_json: bool = False):
        super().__init__(message)
        self.status = status
        self.retryable = retryable
        self.retry_after = retry_after  # seconds the server asked us to wait, if it said
        self.invalid_json = invalid_json


class LLMClient:
    def __init__(self, settings: LLMSettings, transport: httpx.BaseTransport | None = None,
                 sleep=time.sleep, clock=time.monotonic):
        # sleep and clock are parameters so tests can check the waits without actually waiting.
        self.settings = settings
        self._sleep = sleep
        self._clock = clock
        headers = {"Authorization": f"Bearer {settings.api_key}"} if settings.api_key else {}
        self._http = httpx.Client(
            base_url=settings.base_url, headers=headers, timeout=TIMEOUT_SECONDS, transport=transport
        )

    def chat_json(self, messages: list[dict]) -> dict:
        body = {
            "model": self.settings.model,
            "messages": messages,
            "temperature": 0,  # same code in, (nearly) same review out
            "response_format": {"type": "json_object"},  # JSON mode: the reply must be JSON
        }
        started = self._clock()
        json_retried = False
        for attempt in range(1, MAX_ATTEMPTS + 1):
            remaining = DEADLINE_SECONDS - (self._clock() - started)
            try:
                return self._attempt(body, timeout=min(TIMEOUT_SECONDS, remaining))
            except LLMError as exc:
                if exc.invalid_json:
                    if json_retried:
                        raise
                    json_retried, wait = True, 0.0  # CLAUDE.md: retry invalid JSON once
                elif exc.retryable:
                    wait = exc.retry_after if exc.retry_after is not None else BACKOFF_SECONDS * 2 ** (attempt - 1)
                else:
                    raise
                if wait > MAX_WAIT_SECONDS:
                    raise LLMError(f"{self.settings.provider} rate limited; retry in {_duration(wait)}",
                                   status=exc.status) from exc
                elapsed = self._clock() - started
                if attempt == MAX_ATTEMPTS or elapsed + wait >= DEADLINE_SECONDS:
                    raise LLMError(f"{exc} (gave up after {attempt} attempts)", status=exc.status) from exc
                self._sleep(wait)
        raise AssertionError("unreachable")  # the loop always returns or raises

    def _attempt(self, body: dict, timeout: float) -> dict:
        provider = self.settings.provider
        try:
            response = self._http.post("chat/completions", json=body, timeout=timeout)
        except httpx.TimeoutException as exc:
            raise LLMError(f"{provider} timed out after {timeout:.0f}s") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"could not reach {provider}: {exc}", retryable=True) from exc

        if response.status_code != 200:
            # Never echo the request back: it carries the API key in a header.
            status = response.status_code
            raise LLMError(
                f"{provider} returned HTTP {status}: {error_detail(response)}",
                status=status,
                retryable=status in RETRYABLE_STATUS,
                retry_after=retry_after_seconds(response) if status == 429 else None,
            )

        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"unexpected response shape from {provider}") from exc
        return parse_json_object(content)


def _duration(seconds: float) -> str:
    """45 -> "45 s", 300 -> "5 min", 20538 -> "5 h 42 min". A daily free-tier quota running out
    shows up as a 429 asking for hours, and "retry after 20538s" means nothing to a user."""
    if seconds < 120:
        return f"{seconds:.0f} s"
    minutes = round(seconds / 60)
    hours, minutes = divmod(minutes, 60)
    if hours == 0:
        return f"{minutes} min"
    return f"{hours} h {minutes} min (daily quota likely used up)"


def _error_body(response: httpx.Response) -> dict | None:
    """OpenAI-style APIs send {"error": {...}}; Gemini wraps that object in a list."""
    try:
        body = response.json()
    except ValueError:
        return None
    if isinstance(body, list) and body:
        body = body[0]
    error = body.get("error") if isinstance(body, dict) else None
    return error if isinstance(error, dict) else None


def error_detail(response: httpx.Response) -> str:
    """The provider's own error message, e.g. "Please pass a valid API key", else raw text."""
    error = _error_body(response)
    if error and "message" in error:
        return str(error["message"])[:200]
    return response.text[:200]


def retry_after_seconds(response: httpx.Response) -> float | None:
    """How long a 429 asks us to wait, or None if it doesn't say.

    The standard place is the Retry-After header (seconds, or an HTTP date). Gemini often puts
    it in the body instead: error.details[] has a RetryInfo entry like {"retryDelay": "17s"}.
    """
    header = response.headers.get("retry-after")
    if header:
        if header.strip().isdigit():
            return float(header)
        try:
            when = parsedate_to_datetime(header)
            return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError):
            pass
    error = _error_body(response) or {}
    for detail in error.get("details") or []:
        delay = detail.get("retryDelay") if isinstance(detail, dict) else None
        match = re.fullmatch(r"(\d+(?:\.\d+)?)s", str(delay or ""))
        if match:
            return float(match.group(1))
    return None


def parse_json_object(content: str | None) -> dict:
    """Parse the model's reply. Strips a ```json fence, which some models add even in JSON mode."""
    text = (content or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMError(f"model reply is not valid JSON: {exc.msg}", invalid_json=True) from exc
    if not isinstance(data, dict):
        raise LLMError("model reply is JSON but not an object", invalid_json=True)
    return data
