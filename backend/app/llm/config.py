"""LLM settings, read from environment variables (and the repo-root .env file).

All three providers speak the OpenAI chat-completions API, so one client works for every
provider and only the base URL, model and key change. That keeps the project on free tiers
and lets us switch providers by editing .env, without touching code.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[3]

# provider -> (base URL, default model). Ollama has no sensible default model: it depends on
# what you've pulled locally, so LLM_MODEL is required for it.
PROVIDERS = {
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini-3.5-flash"),
    "groq": ("https://api.groq.com/openai/v1", "llama-3.3-70b-versatile"),
    "ollama": ("http://localhost:11434/v1", None),
}
NEEDS_KEY = {"gemini", "groq"}


class LLMConfigError(ValueError):
    """Bad LLM settings. Raised at startup so a typo in .env fails loudly, not on first use."""


@dataclass(frozen=True)
class LLMSettings:
    provider: str
    base_url: str
    model: str
    api_key: str | None


def load_settings(env_file: Path | None = REPO_ROOT / ".env") -> LLMSettings | None:
    """Return the configured LLM, or None when LLM_PROVIDER is off (or unset).

    Tests pass env_file=None so a developer's real .env can't leak into them.
    """
    if env_file is not None:
        # override=False: a variable already set in the real environment wins over .env.
        # That's how tests/conftest.py forces LLM_PROVIDER=off even when .env has a real key.
        load_dotenv(env_file, override=False)

    provider = os.getenv("LLM_PROVIDER", "off").strip().lower()
    if provider in ("", "off"):
        return None
    if provider not in PROVIDERS:
        raise LLMConfigError(f"LLM_PROVIDER={provider!r}; expected one of gemini, groq, ollama, off")

    base_url, default_model = PROVIDERS[provider]
    model = os.getenv("LLM_MODEL", "").strip() or default_model
    if not model:
        raise LLMConfigError(f"LLM_MODEL is required for provider {provider!r}")

    # The provider's own key (GROQ_API_KEY, GEMINI_API_KEY) wins over the generic LLM_API_KEY.
    # That lets .env hold keys for several providers, and switching LLM_PROVIDER can never send
    # one provider's key to another provider's servers.
    provider_key = f"{provider.upper()}_API_KEY"
    api_key = os.getenv(provider_key, "").strip() or os.getenv("LLM_API_KEY", "").strip() or None
    if provider in NEEDS_KEY and not api_key:
        raise LLMConfigError(f"{provider_key} or LLM_API_KEY is required for provider {provider!r}")

    return LLMSettings(provider=provider, base_url=base_url, model=model, api_key=api_key)
