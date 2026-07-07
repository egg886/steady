"""LLM integration module for steady.

Provides AI-powered code repair when AST repair alone isn't enough.
Supports OpenAI, Anthropic, and custom callable backends.

Without an API key, :meth:`LLMClient.repair` returns ``None`` — steady
falls back to AST-only repair.

The prompt asks the model to return a **JSON object** with the shape::

    {
        "fixed_code": "...",
        "explanation": "...",
        "strategy": "..."
    }

so that steady can record a meaningful, human-readable explanation in the
Bug Tour Report. Older plain-code responses are still accepted for
backward compatibility with custom callables that return raw source.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from .config import Config, get_config

logger = logging.getLogger("steady")

#: System prompt reused across all backends. Describes the assistant role,
#: the JSON contract, and the constraints (minimal patch, no extra prose).
SYSTEM_PROMPT: str = (
    "You are an expert Python code repair assistant integrated into "
    "`steady`, an AI-native fault-tolerant runtime.\n"
    "\n"
    "Your job: given a function that raised an exception, return the "
    "minimal source-code patch that makes the function run successfully "
    "while preserving its original intent and return value.\n"
    "\n"
    "Rules:\n"
    "1. Output ONLY a single JSON object. No markdown, no code fences, "
    "no commentary outside the JSON.\n"
    "2. The JSON must have exactly these keys:\n"
    '   - "fixed_code": the complete repaired function source (a valid '
    "Python `def` statement, starting from `def`).\n"
    '   - "explanation": a short, human-readable description of what was '
    "wrong and how you fixed it. Keep it under 2 sentences.\n"
    '   - "strategy": a compact tag for the repair technique, one of: '
    '"remove_line", "fix_value", "add_import", "fix_syntax", '
    '"add_guard", "rewrite_logic", "other".\n'
    "3. Make the smallest possible change. Do not refactor unrelated "
    "code, rename variables, or alter the function signature.\n"
    "4. Keep the function name identical to the original so steady can "
    "recompile and re-execute it.\n"
    "5. If the error message is in a non-English language (e.g. Chinese), "
    "treat it as a normal Python exception message — match it to the "
    "standard Python error type and fix accordingly. You may write the "
    "`explanation` in the same language as the error message.\n"
    "6. Never include `import steady` or steady-specific calls in the "
    "fixed code.\n"
)

#: Template describing the required JSON output contract, appended to the
#: user prompt so models that ignore the system message still comply.
JSON_CONTRACT: str = (
    "Respond with ONLY this JSON shape (no markdown fences, no extra "
    "text):\n"
    "{\n"
    '  "fixed_code": "<complete repaired function source>",\n'
    '  "explanation": "<what was wrong and how you fixed it>",\n'
    '  "strategy": "<remove_line|fix_value|add_import|fix_syntax|'
    'add_guard|rewrite_logic|other>"\n'
    "}\n"
)


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

    def __init__(self, config: Config | None = None) -> None:
        """Initialise the client.

        Args:
            config: Optional :class:`Config` instance. Defaults to the
                process-wide singleton returned by :func:`get_config`.
        """
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
        context: dict[str, Any] | None = None,
    ) -> LLMRepairResult | None:
        """Send code + error to the LLM and get back a fix.

        Returns ``None`` if no API key or custom callable is configured,
        or if the backend raises an error.

        Args:
            source: The source code that caused the error.
            error_type: The exception class name.
            error_msg: The exception message (may be in any language,
                including Chinese).
            traceback_str: Formatted traceback string.
            context: Additional context (function name, signature, args,
                kwargs, etc.).

        Returns:
            An :class:`LLMRepairResult` if successful, ``None`` otherwise.
        """
        # Check if we have any LLM backend configured
        if self._config.llm_client is not None:
            logger.debug("LLM repair: calling custom callable backend")
            prompt = self._build_prompt(
                source, error_type, error_msg, traceback_str, context
            )
            try:
                response, tokens = self._call_custom(prompt)
                return self._parse_response(response, tokens)
            except Exception:
                logger.debug("LLM repair: custom callable raised", exc_info=True)
                return None

        if not self._config.api_key:
            return None

        logger.debug(
            "LLM repair: calling %s backend (model=%s)",
            self._config.provider,
            self._config.model,
        )
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
            logger.debug(
                "LLM repair: %s backend raised", self._config.provider, exc_info=True
            )
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
        context: dict[str, Any] | None,
    ) -> str:
        """Build the user prompt sent to the LLM.

        The prompt bundles the failing source, the exception (type, message
        and traceback) and any runtime context (function name, signature,
        argument values). Error messages in any language — including
        Chinese — are passed through verbatim so the model can match them
        against the standard Python error type.

        Args:
            source: The failing function source.
            error_type: The exception class name.
            error_msg: The exception message (any language).
            traceback_str: Formatted traceback string.
            context: Optional dict of extra context.

        Returns:
            The fully assembled user prompt string.
        """
        context_str = self._format_context(context)

        return (
            "Repair the following Python function so it runs without "
            "errors. Keep the change minimal and preserve the function "
            "name and signature.\n"
            "\n"
            f"## Exception\n"
            f"- Type: {error_type}\n"
            f"- Message: {error_msg}\n"
            "\n"
            f"## Traceback\n"
            f"```\n{traceback_str}\n```\n"
            "\n"
            f"## Failing source code\n"
            f"```python\n{source}\n```\n"
            f"{context_str}"
            "\n"
            "## Requirements\n"
            "- Return the COMPLETE function source (a valid `def` "
            "statement).\n"
            "- Do not add imports for steady.\n"
            "- Do not wrap the code in markdown fences inside the JSON "
            "string value.\n"
            "\n"
            f"{JSON_CONTRACT}"
        )

    @staticmethod
    def _format_context(context: dict[str, Any] | None) -> str:
        """Format the runtime context dict into a prompt section.

        Args:
            context: A dict that may contain keys such as ``function``,
                ``signature``, ``args`` and ``kwargs``.

        Returns:
            A markdown-formatted context section, or an empty string when
            no context is supplied.
        """
        if not context:
            return ""

        lines: list[str] = ["## Runtime context"]
        for key, value in context.items():
            lines.append(f"- {key}: {value}")
        lines.append("")
        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    # Backend calls
    # ------------------------------------------------------------------
    def _call_openai(self, prompt: str) -> tuple[str, int]:
        """Call the OpenAI Chat Completions API.

        Args:
            prompt: The fully assembled user prompt.

        Returns:
            A ``(response_text, tokens_used)`` tuple.
        """
        from openai import OpenAI

        client = OpenAI(api_key=self._config.api_key)
        response = client.chat.completions.create(
            model=self._config.model,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        text = response.choices[0].message.content or ""
        tokens = response.usage.total_tokens if response.usage else 0
        return text, tokens

    def _call_anthropic(self, prompt: str) -> tuple[str, int]:
        """Call the Anthropic Messages API.

        Args:
            prompt: The fully assembled user prompt.

        Returns:
            A ``(response_text, tokens_used)`` tuple.
        """
        import anthropic

        client = anthropic.Anthropic(api_key=self._config.api_key)
        message = client.messages.create(
            model=self._config.model,
            max_tokens=2048,
            temperature=0,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        # message.content is a list of content blocks (TextBlock,
        # ThinkingBlock, ToolUseBlock, etc.). Only TextBlock has a
        # ``text`` attribute, so use getattr for safe access.
        text = ""
        if message.content:
            text = getattr(message.content[0], "text", "") or ""
        tokens = message.usage.input_tokens + message.usage.output_tokens
        return text, tokens

    def _call_custom(self, prompt: str) -> tuple[str, int]:
        """Call a user-supplied custom LLM callable.

        The callable receives the full prompt string (which already embeds
        the system instructions) and may return either a plain ``str``
        (the response text) or a ``(response, tokens)`` tuple.

        Args:
            prompt: The fully assembled prompt.

        Returns:
            A ``(response_text, tokens_used)`` tuple.
        """
        # Prepend the system prompt so custom backends also see the role
        # description and the JSON contract.
        full_prompt = f"{SYSTEM_PROMPT}\n\n{prompt}"
        llm = self._config.llm_client
        if llm is None:
            raise RuntimeError("No custom LLM callable configured")
        result = llm(full_prompt)
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
    ) -> LLMRepairResult | None:
        """Parse the LLM response into an :class:`LLMRepairResult`.

        Accepts, in order of preference:

        1. A JSON object (with or without markdown ``json`` fences)
           containing ``fixed_code``, ``explanation`` and ``strategy``.
        2. A raw code block wrapped in markdown fences (backward compat
           with older custom callables that return plain code).

        Args:
            response: The raw model response text.
            tokens: Tokens consumed by the call.

        Returns:
            An :class:`LLMRepairResult`, or ``None`` if the response is
            empty or unparseable.
        """
        if not response or not response.strip():
            return None

        text = response.strip()

        # --- Strategy 1: try to extract a JSON object -------------------
        json_obj = self._extract_json(text)
        if json_obj is not None:
            return self._result_from_json(json_obj, tokens)

        # --- Strategy 2: fall back to raw code (with optional fences) ---
        code = self._strip_code_fences(text)
        if not code:
            return None

        return LLMRepairResult(
            fixed_code=code,
            explanation="LLM-generated fix (raw code response).",
            strategy="llm_repair",
            success=True,
            tokens_used=tokens,
        )

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any] | None:
        """Extract the first JSON object found in *text*.

        Handles three shapes:
          * bare JSON,
          * JSON inside a ```json fenced block,
          * JSON inside a plain ``` fenced block.

        Args:
            text: The raw model response.

        Returns:
            The parsed dict, or ``None`` if no valid JSON object is found.
        """
        candidates: list[str] = []

        # 1. Code-fenced JSON (```json ... ``` or ``` ... ```)
        fence_pattern = re.compile(
            r"```(?:json)?\s*\n?(.*?)```",
            re.DOTALL | re.IGNORECASE,
        )
        for match in fence_pattern.finditer(text):
            candidates.append(match.group(1).strip())

        # 2. The whole text as JSON.
        candidates.append(text)

        for candidate in candidates:
            # Locate the first balanced top-level JSON object.
            obj = LLMClient._find_first_json_object(candidate)
            if obj is not None:
                return obj
        return None

    @staticmethod
    def _find_first_json_object(text: str) -> dict[str, Any] | None:
        """Find and parse the first balanced ``{...}`` object in *text*.

        If the first candidate fails to parse, subsequent ``{...}`` objects
        are tried so that explanatory prose before the JSON (or multiple
        objects) does not prevent extraction.

        Args:
            text: Text that may contain a JSON object.

        Returns:
            The parsed dict, or ``None`` if no valid object is found.
        """
        search_start = 0
        while True:
            start = text.find("{", search_start)
            if start == -1:
                return None

            depth = 0
            in_string = False
            escape = False
            found = False
            for index in range(start, len(text)):
                char = text[index]
                if in_string:
                    if escape:
                        escape = False
                    elif char == "\\":
                        escape = True
                    elif char == '"':
                        in_string = False
                else:
                    if char == '"':
                        in_string = True
                    elif char == "{":
                        depth += 1
                    elif char == "}":
                        depth -= 1
                        if depth == 0:
                            snippet = text[start : index + 1]
                            try:
                                parsed = json.loads(snippet)
                            except (ValueError, TypeError):
                                # Try the next { ... } object
                                search_start = index + 1
                                found = True
                                break
                            if isinstance(parsed, dict):
                                return parsed
                            search_start = index + 1
                            found = True
                            break
            if not found:
                # Ran off the end without finding a balanced object
                return None

    @staticmethod
    def _result_from_json(
        obj: dict[str, Any], tokens: int
    ) -> LLMRepairResult | None:
        """Build an :class:`LLMRepairResult` from a parsed JSON dict.

        Args:
            obj: Dict expected to contain ``fixed_code``.
            tokens: Tokens consumed by the call.

        Returns:
            An :class:`LLMRepairResult`, or ``None`` if no fixed code is
            present.
        """
        fixed_code = obj.get("fixed_code")
        if not fixed_code or not str(fixed_code).strip():
            return None

        return LLMRepairResult(
            fixed_code=str(fixed_code).strip(),
            explanation=str(obj.get("explanation") or "LLM-generated fix."),
            strategy=str(obj.get("strategy") or "llm_repair"),
            success=True,
            tokens_used=tokens,
        )

    @staticmethod
    def _strip_code_fences(text: str) -> str:
        """Strip markdown code fences and surrounding whitespace.

        Args:
            text: Raw text that may be wrapped in ``` fences.

        Returns:
            The inner code, stripped of fences and whitespace.
        """
        code = text
        if code.startswith("```python"):
            code = code[len("```python") :]
        elif code.startswith("```json"):
            code = code[len("```json") :]
        elif code.startswith("```"):
            code = code[3:]
        if code.endswith("```"):
            code = code[:-3]
        return code.strip()


def create_llm_client(config: Config | None = None) -> LLMClient:
    """Factory function to create an :class:`LLMClient`.

    Args:
        config: Optional :class:`Config` instance. Defaults to the global
            config singleton.

    Returns:
        A new :class:`LLMClient` instance.
    """
    return LLMClient(config)
