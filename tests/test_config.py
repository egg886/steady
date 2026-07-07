"""Tests for the configuration module."""

from __future__ import annotations

import threading

import pytest

from steady.config import Config, get_config


# ---------------------------------------------------------------------- #
# Environment variable loading
# ---------------------------------------------------------------------- #
def test_env_var_loading(monkeypatch):
    """Config should load from environment variables."""
    monkeypatch.setenv("STEADY_API_KEY", "env-key-123")
    monkeypatch.setenv("STEADY_MODEL", "gpt-4o")
    monkeypatch.setenv("STEADY_PROVIDER", "anthropic")
    monkeypatch.setenv("STEADY_MAX_RETRIES", "7")
    monkeypatch.setenv("STEADY_LOG_LEVEL", "DEBUG")

    config = Config()
    assert config.api_key == "env-key-123"
    assert config.model == "gpt-4o"
    assert config.provider == "anthropic"
    assert config.max_retries == 7
    assert config.log_level == "DEBUG"


def test_env_var_defaults(monkeypatch):
    """Config should use defaults when env vars are not set."""
    monkeypatch.delenv("STEADY_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("STEADY_MODEL", raising=False)
    monkeypatch.delenv("STEADY_PROVIDER", raising=False)
    monkeypatch.delenv("STEADY_MAX_RETRIES", raising=False)
    monkeypatch.delenv("STEADY_ENABLED", raising=False)
    monkeypatch.delenv("STEADY_LOG_LEVEL", raising=False)

    config = Config()
    assert config.api_key is None
    assert config.model == "gpt-4o-mini"
    assert config.provider == "openai"
    assert config.max_retries == 3
    assert config.enabled is True
    assert config.log_level == "WARNING"


def test_api_key_fallback_to_openai(monkeypatch):
    """STEADY_API_KEY not set should fall back to OPENAI_API_KEY."""
    monkeypatch.delenv("STEADY_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-fallback")

    config = Config()
    assert config.api_key == "sk-openai-fallback"


def test_steady_key_takes_priority(monkeypatch):
    """STEADY_API_KEY should take priority over OPENAI_API_KEY."""
    monkeypatch.setenv("STEADY_API_KEY", "steady-priority")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-fallback")

    config = Config()
    assert config.api_key == "steady-priority"


def test_enabled_env_var(monkeypatch):
    """STEADY_ENABLED should control the enabled flag."""
    monkeypatch.setenv("STEADY_ENABLED", "false")
    config = Config()
    assert config.enabled is False

    monkeypatch.setenv("STEADY_ENABLED", "1")
    config2 = Config()
    assert config2.enabled is True


# ---------------------------------------------------------------------- #
# Programmatic configuration
# ---------------------------------------------------------------------- #
def test_programmatic_config():
    """configure() should update fields."""
    config = Config()
    config.configure(api_key="my-key", model="gpt-4o", max_retries=5)
    assert config.api_key == "my-key"
    assert config.model == "gpt-4o"
    assert config.max_retries == 5


def test_configure_partial_update():
    """configure() should only update provided fields."""
    config = Config()
    original_model = config.model
    config.configure(api_key="new-key")
    assert config.api_key == "new-key"
    assert config.model == original_model  # unchanged


def test_configure_enabled():
    """configure(enabled=...) should update the enabled flag."""
    config = Config()
    config.configure(enabled=False)
    assert config.enabled is False
    config.configure(enabled=True)
    assert config.enabled is True


def test_configure_custom_llm():
    """configure(llm=...) should set a custom LLM callable."""
    config = Config()

    def my_llm(prompt):
        return "fixed code", 100

    config.configure(llm=my_llm)
    assert config.llm_client is my_llm


def test_configure_provider():
    """configure(provider=...) should update the provider."""
    config = Config()
    config.configure(provider="anthropic")
    assert config.provider == "anthropic"


# ---------------------------------------------------------------------- #
# Log level
# ---------------------------------------------------------------------- #
def test_log_level_env_var(monkeypatch):
    """STEADY_LOG_LEVEL should be read and upper-cased."""
    monkeypatch.setenv("STEADY_LOG_LEVEL", "info")
    config = Config()
    assert config.log_level == "INFO"


def test_log_level_env_var_invalid(monkeypatch):
    """Invalid STEADY_LOG_LEVEL should fall back to the default."""
    monkeypatch.setenv("STEADY_LOG_LEVEL", "VERBOSE")
    config = Config()
    assert config.log_level == "WARNING"


def test_configure_log_level():
    """configure(log_level=...) should update the log level."""
    config = Config()
    config.configure(log_level="DEBUG")
    assert config.log_level == "DEBUG"


def test_configure_log_level_case_insensitive():
    """configure(log_level=...) should be case-insensitive."""
    config = Config()
    config.configure(log_level="error")
    assert config.log_level == "ERROR"


def test_configure_log_level_invalid():
    """Invalid log_level should be silently ignored."""
    config = Config()
    original = config.log_level
    config.configure(log_level="VERBOSE")
    assert config.log_level == original


# ---------------------------------------------------------------------- #
# Reset
# ---------------------------------------------------------------------- #
def test_reset(monkeypatch):
    """reset() should restore defaults and re-read env vars."""
    monkeypatch.setenv("STEADY_API_KEY", "env-key")
    monkeypatch.delenv("STEADY_MODEL", raising=False)

    config = Config()
    config.configure(api_key="override", model="custom-model", log_level="DEBUG")
    assert config.api_key == "override"
    assert config.model == "custom-model"
    assert config.log_level == "DEBUG"

    config.reset()
    # After reset, should read from env again
    assert config.api_key == "env-key"
    assert config.model == "gpt-4o-mini"  # default
    assert config.log_level == "WARNING"  # default


def test_reset_clears_llm():
    """reset() should clear custom LLM callable."""
    config = Config()
    config.configure(llm=lambda p: "result")
    assert config.llm_client is not None

    config.reset()
    assert config.llm_client is None


# ---------------------------------------------------------------------- #
# Singleton
# ---------------------------------------------------------------------- #
def test_singleton():
    """get_config() should return the same instance."""
    c1 = get_config()
    c2 = get_config()
    assert c1 is c2


# ---------------------------------------------------------------------- #
# Additional configuration scenarios
# ---------------------------------------------------------------------- #
def test_configure_model(monkeypatch):
    """configure(model=...) should update the model identifier."""
    monkeypatch.delenv("STEADY_MODEL", raising=False)
    config = Config()
    assert config.model == "gpt-4o-mini"

    config.configure(model="gpt-4-turbo")
    assert config.model == "gpt-4-turbo"


def test_configure_provider_invalid():
    """Configuring an invalid provider should not crash (stored as-is)."""
    config = Config()
    config.configure(provider="invalid_provider")
    # Stored lowercased; no exception raised.
    assert config.provider == "invalid_provider"


def test_env_var_max_retries_invalid(monkeypatch):
    """Non-numeric STEADY_MAX_RETRIES should fall back to the default."""
    monkeypatch.setenv("STEADY_MAX_RETRIES", "not-a-number")
    config = Config()
    assert config.max_retries == 3


@pytest.mark.parametrize(
    "value,expected",
    [
        ("1", True),
        ("true", True),
        ("yes", True),
        ("on", True),
        ("TRUE", True),
        ("Yes", True),
        ("0", False),
        ("false", False),
        ("no", False),
        ("anything-else", False),
        ("", True),  # empty string keeps the default (True)
    ],
)
def test_env_var_enabled_various(monkeypatch, value, expected):
    """Various STEADY_ENABLED values should map to the correct boolean."""
    monkeypatch.setenv("STEADY_ENABLED", value)
    config = Config()
    assert config.enabled is expected


def test_thread_safety():
    """Concurrent read/write access to Config from many threads should not crash."""
    config = Config()
    errors: list = []

    def worker():
        try:
            for _ in range(100):
                config.configure(api_key="k", model="m", max_retries=5)
                _ = config.api_key
                _ = config.model
                _ = config.enabled
                _ = config.max_retries
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []


def test_llm_client_property():
    """llm_client property should get/set a custom callable."""
    config = Config()
    assert config.llm_client is None

    def my_llm(prompt):
        return "fixed", 10

    config.configure(llm=my_llm)
    assert config.llm_client is my_llm
