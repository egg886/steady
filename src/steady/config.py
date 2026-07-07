"""Configuration management for steady.

This module provides the global :class:`Config` singleton that stores all
runtime configuration for the steady library. Configuration is loaded
automatically from environment variables on first use, and can be overridden
programmatically via :meth:`Config.configure`.

Design principles
------------------
* steady works **without** an API key (AST repair only).
* AI is an enhancement, not a requirement.
* We follow the openai/anthropic SDK pattern: read ``os.environ`` directly
  and **never** read ``.env`` files. ``python-dotenv`` is intentionally an
  end-user concern, not a steady dependency.

Environment variables
----------------------
``STEADY_API_KEY``
    Primary API key. Falls back to ``OPENAI_API_KEY``.

``OPENAI_API_KEY``
    Fallback API key used when ``STEADY_API_KEY`` is not set.

``STEADY_MODEL``
    Model identifier (default: ``gpt-4o-mini``).

``STEADY_PROVIDER``
    LLM provider: ``openai`` or ``anthropic`` (default: ``openai``).

``STEADY_MAX_RETRIES``
    Maximum repair attempts per error (default: ``3``).

``STEADY_ENABLED``
    Master switch. ``"1"``/``"true"``/``"yes"`` enables steady,
    anything else disables it (default: ``true``).
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Callable

__all__ = ["Config", "get_config"]


_TRUTHY = {"1", "true", "yes", "on", "y", "t"}
"""Strings interpreted as boolean ``True`` when reading env vars."""

#: Valid log level names accepted by :func:`logging.getLevelNamesMapping`
#: (Python 3.11+) or the fallback dict below (3.9/3.10).
_LOG_LEVELS = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
    "NOTSET": logging.NOTSET,
}


def _env_bool(name: str, default: bool) -> bool:
    """Read a boolean value from an environment variable.

    The comparison is case-insensitive. Values in :data:`_TRUTHY` map to
    ``True``; the empty string keeps the default; anything else is ``False``.
    """
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in _TRUTHY


def _env_int(name: str, default: int) -> int:
    """Read an integer value from an environment variable.

    Returns *default* if the variable is unset or cannot be parsed as int.
    """
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw.strip())
    except (TypeError, ValueError):
        return default


def _env_log_level(name: str, default: str) -> str:
    """Read a logging level name from an environment variable.

    Returns the uppercased value if it is a recognised level name,
    otherwise *default*.
    """
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    level = raw.strip().upper()
    return level if level in _LOG_LEVELS else default


class Config:
    """Global configuration for steady.

    A single instance is shared process-wide (see :func:`get_config`). The
    class reads from environment variables on construction, and exposes a
    :meth:`configure` method for programmatic overrides. All mutations are
    protected by an internal lock so that concurrent access from multiple
    threads is safe.

    The config object is intentionally permissive: missing API keys do not
    raise. Callers that need an LLM (e.g. :class:`steady.llm.LLMClient`) are
    expected to check :attr:`api_key` and gracefully degrade.
    """

    def __init__(self) -> None:
        # Defaults. ``_auto_load`` will overwrite these from the environment.
        self._api_key: str | None = None
        self._model: str = "gpt-4o-mini"
        self._llm: Callable[..., Any] | None = None  # custom LLM callable
        self._provider: str = "openai"
        self._max_retries: int = 3
        self._enabled: bool = True
        self._log_level: str = "WARNING"
        self._lock = threading.RLock()
        self._auto_load()

    # ------------------------------------------------------------------ #
    # Environment loading
    # ------------------------------------------------------------------ #
    def _auto_load(self) -> None:
        """Auto-load configuration from environment variables.

        API key resolution order:
            ``STEADY_API_KEY`` -> ``OPENAI_API_KEY`` (fallback).

        Also reads ``STEADY_MODEL``, ``STEADY_PROVIDER``,
        ``STEADY_MAX_RETRIES``, ``STEADY_ENABLED`` and ``STEADY_LOG_LEVEL``.
        """
        # API key: STEADY_API_KEY takes priority, OPENAI_API_KEY is fallback.
        self._api_key = os.environ.get("STEADY_API_KEY") or os.environ.get(
            "OPENAI_API_KEY"
        )

        model = os.environ.get("STEADY_MODEL")
        if model:
            self._model = model.strip()

        provider = os.environ.get("STEADY_PROVIDER")
        if provider:
            self._provider = provider.strip().lower()

        self._max_retries = _env_int("STEADY_MAX_RETRIES", 3)
        self._enabled = _env_bool("STEADY_ENABLED", True)
        self._log_level = _env_log_level("STEADY_LOG_LEVEL", "WARNING")

    # ------------------------------------------------------------------ #
    # Programmatic configuration
    # ------------------------------------------------------------------ #
    def configure(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        llm: Callable[..., Any] | None = None,
        provider: str | None = None,
        max_retries: int | None = None,
        enabled: bool | None = None,
        log_level: str | None = None,
    ) -> None:
        """Programmatically update configuration.

        Only the keyword arguments that are provided (i.e. not ``None``)
        are applied; existing values are preserved otherwise. This is safe
        to call multiple times.

        Parameters
        ----------
        api_key:
            Override the LLM API key.
        model:
            Override the model identifier (e.g. ``"gpt-4o"``).
        llm:
            A custom callable used in place of the OpenAI/Anthropic SDKs.
            The callable should accept a prompt string and return either a
            plain text response or a ``(response, tokens)`` tuple.
        provider:
            ``"openai"`` or ``"anthropic"``.
        max_retries:
            Maximum repair attempts per error.
        enabled:
            Master switch. ``False`` disables steady entirely.
        log_level:
            Logging level for steady's internal logger. One of
            ``"DEBUG"``, ``"INFO"``, ``"WARNING"``, ``"ERROR"``,
            ``"CRITICAL"`` (case-insensitive).
        """
        with self._lock:
            if api_key is not None:
                self._api_key = api_key
            if model is not None:
                self._model = model
            if llm is not None:
                self._llm = llm
            if provider is not None:
                self._provider = provider.strip().lower()
            if max_retries is not None:
                self._max_retries = int(max_retries)
            if enabled is not None:
                self._enabled = bool(enabled)
            if log_level is not None:
                level = log_level.strip().upper()
                if level in _LOG_LEVELS:
                    self._log_level = level

    def reset(self) -> None:
        """Reset configuration to defaults and re-read environment variables.

        Custom LLM callables are cleared; all other fields are restored to
        their environment-derived defaults.
        """
        with self._lock:
            self._api_key = None
            self._model = "gpt-4o-mini"
            self._llm = None
            self._provider = "openai"
            self._max_retries = 3
            self._enabled = True
            self._log_level = "WARNING"
            self._auto_load()

    # ------------------------------------------------------------------ #
    # Read-only properties
    # ------------------------------------------------------------------ #
    @property
    def api_key(self) -> str | None:
        """The configured API key, or ``None`` if not set."""
        with self._lock:
            return self._api_key

    @property
    def model(self) -> str:
        """The model identifier used for LLM calls."""
        with self._lock:
            return self._model

    @property
    def max_retries(self) -> int:
        """Maximum number of repair attempts per error."""
        with self._lock:
            return self._max_retries

    @property
    def enabled(self) -> bool:
        """Whether steady's error handling is active."""
        with self._lock:
            return self._enabled

    @property
    def llm_client(self) -> Callable[..., Any] | None:
        """A custom LLM callable supplied by the user, or ``None``."""
        with self._lock:
            return self._llm

    @property
    def provider(self) -> str:
        """The active LLM provider (``"openai"`` or ``"anthropic"``)."""
        with self._lock:
            return self._provider

    @property
    def log_level(self) -> str:
        """The logging level name (e.g. ``"WARNING"``, ``"INFO"``)."""
        with self._lock:
            return self._log_level

    # ------------------------------------------------------------------ #
    # Debug helpers
    # ------------------------------------------------------------------ #
    def __repr__(self) -> str:  # pragma: no cover - trivial
        with self._lock:
            key_display = "***" if self._api_key else None
            return (
                f"Config(api_key={key_display!r}, model={self._model!r}, "
                f"provider={self._provider!r}, max_retries={self._max_retries}, "
                f"enabled={self._enabled}, log_level={self._log_level!r}, "
                f"llm={'custom' if self._llm else None})"
            )


# ---------------------------------------------------------------------- #
# Process-wide singleton (lazy initialisation)
# ---------------------------------------------------------------------- #
_config: Config | None = None
_singleton_lock = threading.Lock()


def get_config() -> Config:
    """Return the process-wide :class:`Config` singleton.

    The singleton is created lazily on first access, which means environment
    variables set after import time (e.g. via ``os.environ`` in a test or
    after ``dotenv.load_dotenv()``) will still be picked up.
    """
    global _config
    if _config is None:
        with _singleton_lock:
            if _config is None:
                _config = Config()
    return _config
