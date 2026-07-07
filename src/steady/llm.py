"""LLM integration module for steady.

Provides AI-powered code repair when AST repair alone isn't enough.
Supports OpenAI, Anthropic, and custom callable backends.

Without an API key, :meth:`LLMClient.repair` returns ``None`` — steady
falls back to AST-only repair.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable, Optional, Tuple

from .config import Config, get_config


@dataclass
class LLMRepairResult:
    """Result of an LLM repair attempt."""

    fixed_code: str
    """The repaired source code."""

    explanation: str
    """Human-readable explanation of the fix."""

    strategy: str
    """Repair strategy: 'remove_line', 'fix_value', 'add_import', etc."""

    success: bool
    """Whether the LLM produced a valid fix."""

    tokens_used: int = 0
    """Number of tokens consumed by the LLM call."""


class LLMClient:
    """Client for AI-powered code repair.

    Delegates to OpenAI, Anthropic, or a custom callable based on config.
    If no API key or custom callable is configured, :meth:`repair` returns
    ``None``.
    """

    def __init__(self, config: Optional[Config] = None) -> None:
        self._config = config or get_config()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def repair(
        self,
        *,
        source: str,
        error_type: str,
        error_msg: str,
        traceback_str: str,
        context: Optional[dict] = None,
    ) -> Optional[LLMRepairResult]:
        """Send code + error to the LLM and get back a fix.

        Returns ``None`` if no API key or custom callable is configured.

        Args:
            source: The source code that caused the error.
            error_type: The exception class name.
            error_msg: The exception message.
            traceback_str: Formatted traceback string.
            context: Additional context (function name, args, etc.).

        Returns:
            An :class:`LLMRepairResult` if successful, ``None`` otherwise.
        """
        # Check if we have any LLM backend configured
        if self._config.llm_client is not None:
            prompt = self._build_prompt(
                source, error_type, error_msg, traceback_str, context
            )
            try:
                response, tokens = self._call_custom(prompt)
                return self._parse_response(response, tokens)
            except Exception:
                return None

        if not self._config.api_key:
            return None

        prompt = self._build_prompt(
            source, error_type, error_msg, traceback_str, context
        )

        try:
            if self._config.provider == "openai":
                response, tokens = self._call_openai(prompt)
            elif self._config.provider == "anthropic":
                response, tokens = self._call_anthropic(prompt)
            else:
                return None

            return self._parse_response(response, tokens)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Prompt building
    # ------------------------------------------------------------------
    def _build_prompt(
        self,
        source: str,
        error_type: str,
        error_msg: str,
        traceback_str: str,
        context: Optional[dict],
    ) -> str:
        """Build the prompt sent to the LLM."""
        context_str = ""
        if context:
            context_str = "\n".join(
                f"  {k}: {v}" for k, v in context.items()
            )

        return (
            "You are a Python code repair assistant. Fix the following code "
            "so it runs without errors.\n\n"
            f"Error: {error_type}: {error_msg}\n\n"
            f"Traceback:\n{traceback_str}\n\n"
            f"Source code:\n```python\n{source}\n```\n\n"
            f"Context:\n{context_str}\n\n"
            "Return ONLY the fixed Python code. No explanations, no markdown "
            "fences. Just the code."
        )

    # ------------------------------------------------------------------
    # Backend calls
    # ------------------------------------------------------------------
    def _call_openai(self, prompt: str) -> Tuple[str, int]:
        """Call the OpenAI API. Returns (response_text, tokens_used)."""
        from openai import OpenAI

        client = OpenAI(api_key=self._config.api_key)
        response = client.chat.completions.create(
            model=self._config.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a Python code repair assistant.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        text = response.choices[0].message.content or ""
        tokens = response.usage.total_tokens if response.usage else 0
        return text, tokens

    def _call_anthropic(self, prompt: str) -> Tuple[str, int]:
        """Call the Anthropic API. Returns (response_text, tokens_used)."""
        import anthropic

        client = anthropic.Anthropic(api_key=self._config.api_key)
        message = client.messages.create(
            model=self._config.model,
            max_tokens=2048,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        text = message.content[0].text if message.content else ""
        tokens = message.usage.input_tokens + message.usage.output_tokens
        return text, tokens

    def _call_custom(self, prompt: str) -> Tuple[str, int]:
        """Call a custom LLM callable. Returns (response_text, tokens_used)."""
        result = self._config.llm_client(prompt)
        if isinstance(result, tuple):
            return result
        if isinstance(result, str):
            return result, 0
        return str(result), 0

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------
    def _parse_response(
        self, response: str, tokens: int
    ) -> Optional[LLMRepairResult]:
        """Parse the LLM response into an LLMRepairResult."""
        if not response or not response.strip():
            return None

        # Strip markdown code fences if present
        code = response.strip()
        if code.startswith("```python"):
            code = code[len("```python") :]
        elif code.startswith("```"):
            code = code[3:]
        if code.endswith("```"):
            code = code[:-3]
        code = code.strip()

        if not code:
            return None

        return LLMRepairResult(
            fixed_code=code,
            explanation="LLM-generated fix",
            strategy="llm_repair",
            success=True,
            tokens_used=tokens,
        )


def create_llm_client(config: Optional[Config] = None) -> LLMClient:
    """Factory function to create an LLMClient.

    Args:
        config: Optional Config instance. Defaults to the global config.

    Returns:
        A new :class:`LLMClient` instance.
    """
    return LLMClient(config)
