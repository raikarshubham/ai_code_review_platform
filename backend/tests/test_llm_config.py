import pytest

from app.llm.config import LLMConfigError, load_settings


@pytest.fixture
def env(monkeypatch):
    """Start every test from a clean slate of LLM_* variables."""
    for name in ("LLM_PROVIDER", "LLM_API_KEY", "LLM_MODEL", "GEMINI_API_KEY", "GROQ_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def settings(env, **values):
    for name, value in values.items():
        env.setenv(name, value)
    return load_settings(env_file=None)


def test_off_and_unset_mean_no_llm(env):
    assert settings(env) is None
    assert settings(env, LLM_PROVIDER="off") is None


def test_gemini_defaults(env):
    result = settings(env, LLM_PROVIDER="gemini", LLM_API_KEY="k")
    assert result.base_url == "https://generativelanguage.googleapis.com/v1beta/openai"
    assert result.model == "gemini-3.5-flash-lite"
    assert result.api_key == "k"


def test_groq_defaults_and_model_override(env):
    assert settings(env, LLM_PROVIDER="groq", LLM_API_KEY="k").model == "llama-3.3-70b-versatile"
    assert settings(env, LLM_PROVIDER="GROQ", LLM_MODEL="other").model == "other"


def test_missing_key_fails_at_startup(env):
    with pytest.raises(LLMConfigError, match="LLM_API_KEY"):
        settings(env, LLM_PROVIDER="gemini")


def test_ollama_needs_a_model_but_no_key(env):
    with pytest.raises(LLMConfigError, match="LLM_MODEL"):
        settings(env, LLM_PROVIDER="ollama")
    result = settings(env, LLM_PROVIDER="ollama", LLM_MODEL="qwen2.5-coder")
    assert (result.base_url, result.api_key) == ("http://localhost:11434/v1", None)


def test_unknown_provider(env):
    with pytest.raises(LLMConfigError, match="openai"):
        settings(env, LLM_PROVIDER="openai")


def test_provider_specific_key_is_used(env):
    assert settings(env, LLM_PROVIDER="groq", GROQ_API_KEY="groq-key").api_key == "groq-key"


def test_provider_specific_key_wins_so_keys_never_cross_providers(env):
    # .env holds the Gemini key in LLM_API_KEY; switching to Groq must not send it to Groq.
    result = settings(env, LLM_PROVIDER="groq", LLM_API_KEY="gemini-key", GROQ_API_KEY="groq-key")
    assert result.api_key == "groq-key"


def test_generic_key_is_the_fallback(env):
    assert settings(env, LLM_PROVIDER="gemini", LLM_API_KEY="generic").api_key == "generic"


def test_missing_key_error_names_both_variables(env):
    with pytest.raises(LLMConfigError, match="GROQ_API_KEY or LLM_API_KEY"):
        settings(env, LLM_PROVIDER="groq")
