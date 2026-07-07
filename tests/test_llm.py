"""Tests for the LLM integration module.

None of these tests require a real API key — they either exercise the
"no key" path or use a custom callable injected via ``Config.configure``.
"""

from __future__ import annotations

import pytest

from steady.config import Config
from steady.llm import LLMClient, LLMRepairResult, create_llm_client


# ---------------------------------------------------------------------- #
# Fixtures
# ---------------------------------------------------------------------- #
@pytest.fixture
def clean_config(monkeypatch):
    """Return a Config with no API key and no custom LLM."""
    monkeypatch.delenv("STEADY_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    return Config()


# Common kwargs used by every ``client.repair`` call below.
REPAIR_KWARGS = {
    "source": "def f():\n    return 1 / 0\n",
    "error_type": "ZeroDivisionError",
    "error_msg": "division by zero",
    "traceback_str": "Traceback (most recent call last):\n  ...\nZeroDivisionError: division by zero",
    "context": {"function": "f", "args": "()", "kwargs": "()"},
}


# ---------------------------------------------------------------------- #
# No API key
# ---------------------------------------------------------------------- #
def test_repair_without_api_key_returns_none(clean_config):
    """repair() should return None when no API key or custom callable is set."""
    assert clean_config.api_key is None
    assert clean_config.llm_client is None

    client = LLMClient(clean_config)
    result = client.repair(**REPAIR_KWARGS)
    assert result is None


# ---------------------------------------------------------------------- #
# Custom callable
# ---------------------------------------------------------------------- #
def test_repair_with_custom_llm(clean_config):
    """repair() with a custom callable returning a plain string."""
    def fake_llm(prompt):
        return "def f():\n    return 42\n"

    clean_config.configure(llm=fake_llm)
    client = LLMClient(clean_config)

    result = client.repair(**REPAIR_KWARGS)
    assert result is not None
    assert isinstance(result, LLMRepairResult)
    assert result.success is True
    assert "return 42" in result.fixed_code
    # A plain-string response carries no token count.
    assert result.tokens_used == 0


def test_repair_with_custom_llm_returns_tuple(clean_config):
    """repair() with a custom callable returning a (response, tokens) tuple."""
    def fake_llm(prompt):
        return "def f():\n    return 42\n", 77

    clean_config.configure(llm=fake_llm)
    client = LLMClient(clean_config)

    result = client.repair(**REPAIR_KWARGS)
    assert result is not None
    assert result.success is True
    assert result.tokens_used == 77
    assert "return 42" in result.fixed_code


def test_repair_with_custom_llm_exception(clean_config):
    """repair() should return None when the custom callable raises."""
    def bad_llm(prompt):
        raise RuntimeError("LLM exploded")

    clean_config.configure(llm=bad_llm)
    client = LLMClient(clean_config)

    result = client.repair(**REPAIR_KWARGS)
    assert result is None


# ---------------------------------------------------------------------- #
# Response parsing
# ---------------------------------------------------------------------- #
def test_parse_response_strips_markdown(clean_config):
    """_parse_response should strip markdown code fences."""
    client = LLMClient(clean_config)
    result = client._parse_response("```python\ndef f():\n    return 42\n```", 0)
    assert result is not None
    assert result.fixed_code == "def f():\n    return 42"

    # Also handle bare ``` fences.
    result2 = client._parse_response("```\ndef f():\n    return 42\n```", 5)
    assert result2 is not None
    assert result2.tokens_used == 5


def test_parse_response_empty(clean_config):
    """_parse_response should return None for empty / whitespace-only responses."""
    client = LLMClient(clean_config)
    assert client._parse_response("", 0) is None
    assert client._parse_response("   \n  ", 0) is None
    # Only fences, no code inside.
    assert client._parse_response("``````", 0) is None


# ---------------------------------------------------------------------- #
# Prompt building
# ---------------------------------------------------------------------- #
def test_build_prompt_contains_error_info(clean_config):
    """_build_prompt should include the error type, message, source and context."""
    client = LLMClient(clean_config)
    prompt = client._build_prompt(
        source="def f():\n    return 1 / 0\n",
        error_type="ZeroDivisionError",
        error_msg="division by zero",
        traceback_str="Traceback (most recent call last):\n  File ...",
        context={"function": "f", "args": "(1,)", "kwargs": "()"},
    )
    assert "ZeroDivisionError" in prompt
    assert "division by zero" in prompt
    assert "def f():" in prompt
    assert "Traceback" in prompt
    assert "function: f" in prompt
    assert "args: (1,)" in prompt


# ---------------------------------------------------------------------- #
# Factory
# ---------------------------------------------------------------------- #
def test_create_llm_client(clean_config):
    """create_llm_client should return an LLMClient instance."""
    client = create_llm_client(clean_config)
    assert isinstance(client, LLMClient)

    # Without an explicit config it should fall back to the global config.
    client2 = create_llm_client()
    assert isinstance(client2, LLMClient)
