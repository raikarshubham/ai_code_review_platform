import pytest

from app.llm.config import LLMConfigError, load_settings


@pytest.fixture
def env(monkeypatch):
    """Start every test from a clean slate of LLM_* variables."""
    for name in ("LLM_PROVIDER", "LLM_API_KEY", "LLM_MODEL"):
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
    assert result.model == "gemini-3.5-flash"
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
