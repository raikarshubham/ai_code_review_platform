"""Minimal OpenAI-compatible chat client that asks for, and returns, a JSON object.

We call the HTTP API directly with httpx instead of using a provider SDK: one small client
covers Gemini, Groq and Ollama, and tests can swap the network for httpx.MockTransport.
"""

import json

import httpx

from app.llm.config import LLMSettings

TIMEOUT_SECONDS = 60


class LLMError(Exception):
    """The LLM call failed or returned something unusable. The pipeline turns this into
    `ai_review.error` and still returns the static results."""


class LLMClient:
    def __init__(self, settings: LLMSettings, transport: httpx.BaseTransport | None = None):
        self.settings = settings
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
        try:
            response = self._http.post("chat/completions", json=body)
        except httpx.TimeoutException as exc:
            raise LLMError(f"{self.settings.provider} timed out after {TIMEOUT_SECONDS}s") from exc
        except httpx.HTTPError as exc:
            raise LLMError(f"could not reach {self.settings.provider}: {exc}") from exc

        if response.status_code != 200:
            # Never echo the request back: it carries the API key in a header.
            detail = error_detail(response)
            raise LLMError(f"{self.settings.provider} returned HTTP {response.status_code}: {detail}")

        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"unexpected response shape from {self.settings.provider}") from exc
        return parse_json_object(content)


def error_detail(response: httpx.Response) -> str:
    """The provider's own error message, e.g. "Please pass a valid API key", else raw text.

    OpenAI-style APIs send {"error": {"message": ...}}; Gemini wraps that object in a list.
    """
    try:
        body = response.json()
        if isinstance(body, list) and body:
            body = body[0]
        return str(body["error"]["message"])[:200]
    except (ValueError, KeyError, TypeError):
        return response.text[:200]


def parse_json_object(content: str | None) -> dict:
    """Parse the model's reply. Strips a ```json fence, which some models add even in JSON mode."""
    text = (content or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMError(f"model reply is not valid JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise LLMError("model reply is JSON but not an object")
    return data
