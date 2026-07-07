"""Bug Tour Report module for steady.

Uses the 'tour guide / scenic spot / ticket' metaphor:

    - report_id  = ticket (your entry to the bug tour)
    - bugs       = scenic spots (each bug is a stop on the tour)
    - fixes      = tour commentary (what went wrong and how we fixed it)

The Markdown export is enriched with emoji icons, a risk rating and a
summary section (fix success rate, average retry count, token toll) so the
report is pleasant to read both in a terminal and in a Markdown renderer.
Unicode (including CJK) content is preserved verbatim.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

# ---------------------------------------------------------------------- #
# Risk rating
# ---------------------------------------------------------------------- #
#: Mapping from a risk level to its (emoji, label, description).
_RISK_INFO: dict[str, tuple[str, str]] = {
    "none": ("\U0001f917", "None"),
    "low": ("\u2705", "Low"),
    "medium": ("\u26a0\ufe0f", "Medium"),
    "high": ("\u2696\ufe0f", "High"),
    "critical": ("\ud83d\udca5", "Critical"),
}

#: Error types that suggest a more serious problem (logic errors rather
#: than a stray debug line). Each unresolved error of one of these types
#: bumps the risk level by one tier.
_SEVERE_ERROR_TYPES: frozenset[str] = frozenset(
    {
        "TypeError",
        "ValueError",
        "KeyError",
        "AttributeError",
        "RuntimeError",
        "RecursionError",
        "OverflowError",
        "MemoryError",
        "SystemError",
    }
)

#: Emoji used per entry in the Markdown report.
_STATUS_EMOJI: dict[str, str] = {
    "resolved": "\u2705",  # check mark
    "unresolved": "\u274c",  # cross mark
}

#: Emoji used per fix strategy in the Markdown report.
_STRATEGY_EMOJI: dict[str, str] = {
    "ast_repair": "\u2702\ufe0f",  # scissors
    "llm_repair": "\ud83e\udde0",  # brain
    "failed": "\ud83d\uded1",  # no entry
}


@dataclass
class BugEntry:
    """A single bug entry in the Bug Tour Report.

    Represents one scenic spot on the bug tour: what went wrong,
    how it was fixed, and whether the fix succeeded.
    """

    error_type: str
    """Type of the error, e.g., 'ZeroDivisionError'."""

    location: str
    """Where the bug occurred, e.g., 'file.py:42 in function_name'."""

    explanation: str
    """What went wrong (human-readable)."""

    fix_strategy: str
    """How steady tried to fix it: 'ast_repair', 'llm_repair', or 'failed'."""

    fix_description: str
    """Human-readable description of the applied fix."""

    retry_count: int
    """How many retries were needed."""

    resolved: bool
    """Whether the fix succeeded."""

    timestamp: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )
    """ISO timestamp of when the entry was recorded."""


class BugReport:
    """Collects and exports bug entries as a Bug Tour Report.

    The report uses a tourism metaphor: each bug is a scenic spot,
    each fix is tour commentary, and the report ID is your ticket.

    The Markdown export now includes:

    * Emoji icons for status and repair strategy.
    * A *risk rating* derived from the bug count and the error types.
    * A summary section with fix success rate and average retry count.
    """

    def __init__(self) -> None:
        """Initialise an empty report with a fresh ticket ID."""
        self._entries: list[BugEntry] = []
        self._start_time: datetime = datetime.now()
        self._total_tokens: int = 0
        self._report_id: str = (
            f"STEADY-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        )
        self._lock = threading.RLock()

    def add_entry(self, entry: BugEntry) -> None:
        """Add a bug entry to the report.

        Args:
            entry: The :class:`BugEntry` to append.
        """
        with self._lock:
            self._entries.append(entry)

    def add_tokens(self, count: int) -> None:
        """Record LLM tokens used.

        Args:
            count: Number of tokens to add to the running total.
        """
        with self._lock:
            self._total_tokens += count

    def export(
        self, format: Literal["markdown", "json", "dict"] = "markdown"
    ) -> str | dict[str, Any]:
        """Export the full Bug Tour Report.

        Uses the tourism metaphor: report_id = ticket, bugs = scenic spots,
        fixes = tour commentary.

        Args:
            format: Output format - "markdown", "json", or "dict".

        Returns:
            The report as a string (markdown/json) or dict.
        """
        if format == "dict":
            return self.summary()

        if format == "json":
            return json.dumps(self.summary(), indent=2, ensure_ascii=False)

        return self._export_markdown()

    # ------------------------------------------------------------------
    # Markdown export
    # ------------------------------------------------------------------
    def _export_markdown(self) -> str:
        """Render the report as a Markdown string with emoji and a summary.

        Returns:
            The Markdown-formatted Bug Tour Report.
        """
        # Snapshot the entries under the lock to avoid race conditions
        # during the (potentially slow) markdown rendering.
        with self._lock:
            entries = list(self._entries)
            total_tokens = self._total_tokens

        resolved_count = sum(1 for e in entries if e.resolved)
        risk_level = self.risk_level
        risk_emoji, risk_label = _RISK_INFO[risk_level]
        success_rate = self.success_rate

        lines: list[str] = []
        lines.append("# \U0001f9f9 Bug Tour Report")
        lines.append("")
        lines.append("> *稳住，代码能跑 — Stay steady, the code runs.*")  # noqa: RUF001
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## \U0001f3ab Ticket")
        lines.append("")
        lines.append("| Field | Value |")
        lines.append("| --- | --- |")
        lines.append(f"| **Ticket ID** | `{self._report_id}` |")
        lines.append(
            f"| **Duration** | {self.duration_seconds:.2f}s |"
        )
        lines.append(f"| **Scenic spots (bugs)** | {len(entries)} |")
        lines.append(
            f"| **Resolved** | {resolved_count} / {len(entries)} |"
        )
        if total_tokens > 0:
            lines.append(
                f"| **LLM tokens used** | {total_tokens} |"
            )
        lines.append(
            f"| **Risk rating** | {risk_emoji} {risk_label} |"
        )
        lines.append("")

        if not entries:
            lines.append(
                "\U0001f3b2 *No bugs encountered. "
                "The tour was uneventful — keep coding!*"
            )
            return "\n".join(lines)

        # --- Tour stops ----------------------------------------------
        lines.append("## \U0001f4cd Tour Stops")
        lines.append("")
        for i, entry in enumerate(entries, 1):
            status_key = "resolved" if entry.resolved else "unresolved"
            status_emoji = _STATUS_EMOJI[status_key]
            strategy_emoji = _STRATEGY_EMOJI.get(
                entry.fix_strategy, "\u2754"
            )
            lines.append(
                f"### {status_emoji} Stop {i}: {entry.error_type}"
            )
            lines.append("")
            lines.append(f"- **Location:** `{entry.location}`")
            lines.append(f"- **What happened:** {entry.explanation}")
            lines.append(
                f"- **Fix strategy:** {strategy_emoji} "
                f"`{entry.fix_strategy}`"
            )
            lines.append(
                f"- **Tour commentary:** {entry.fix_description}"
            )
            lines.append(f"- **Retries:** {entry.retry_count}")
            lines.append(f"- **Status:** {status_key}")
            lines.append(f"- **Timestamp:** {entry.timestamp}")
            lines.append("")

        # --- Summary --------------------------------------------------
        lines.append("---")
        lines.append("")
        lines.append("## \U0001f4ca Summary")
        lines.append("")
        lines.append("| Metric | Value |")
        lines.append("| --- | --- |")
        lines.append(f"| Total bugs | {len(entries)} |")
        lines.append(f"| Resolved | {resolved_count} |")
        lines.append(
            f"| Unresolved | {len(entries) - resolved_count} |"
        )
        lines.append(f"| Fix success rate | {success_rate:.1f}% |")
        lines.append(f"| Average retries | {self.average_retries:.2f} |")
        lines.append(f"| Risk rating | {risk_emoji} {risk_label} |")
        if total_tokens > 0:
            lines.append(f"| LLM tokens used | {total_tokens} |")
        lines.append(f"| Duration | {self.duration_seconds:.2f}s |")
        lines.append("")

        # Breakdown by error type
        type_counts = self._count_by_field("error_type")
        if type_counts:
            lines.append("**Bugs by error type:**")
            lines.append("")
            for etype, count in type_counts:
                lines.append(f"- `{etype}`: {count}")
            lines.append("")

        # Breakdown by fix strategy
        strategy_counts = self._count_by_field("fix_strategy")
        if strategy_counts:
            lines.append("**Bugs by fix strategy:**")
            lines.append("")
            for strat, count in strategy_counts:
                lines.append(f"- `{strat}`: {count}")
            lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Aggregations / risk rating
    # ------------------------------------------------------------------
    @property
    def risk_level(self) -> str:
        """Compute a risk level from the bug count and error types.

        Heuristic:

        * ``0`` bugs -> ``none``.
        * ``1-2`` bugs -> ``low``.
        * ``3-5`` bugs -> ``medium``.
        * ``6-10`` bugs -> ``high``.
        * ``> 10`` bugs -> ``critical``.

        Any *unresolved* bug of a severe type (TypeError, ValueError, ...)
        bumps the level by one tier (capped at ``critical``).
        """
        with self._lock:
            if self.bug_count == 0:
                return "none"

            if self.bug_count <= 2:
                level = "low"
            elif self.bug_count <= 5:
                level = "medium"
            elif self.bug_count <= 10:
                level = "high"
            else:
                level = "critical"

            severity_bump = any(
                not e.resolved and e.error_type in _SEVERE_ERROR_TYPES
                for e in self._entries
            )
            if severity_bump:
                order = ["none", "low", "medium", "high", "critical"]
                idx = min(order.index(level) + 1, len(order) - 1)
                level = order[idx]
            return level

    @property
    def success_rate(self) -> float:
        """Percentage of bugs that were resolved (``0.0``-``100.0``)."""
        with self._lock:
            if self.bug_count == 0:
                return 100.0
            resolved = sum(1 for e in self._entries if e.resolved)
            return (resolved / self.bug_count) * 100.0

    @property
    def average_retries(self) -> float:
        """Mean number of retries across all entries."""
        with self._lock:
            if self.bug_count == 0:
                return 0.0
            total = sum(e.retry_count for e in self._entries)
            return total / self.bug_count

    def _count_by_field(self, field_name: str) -> list[tuple[str, int]]:
        """Count entries grouped by a BugEntry field.

        Args:
            field_name: The name of the :class:`BugEntry` attribute to
                group by (e.g. ``"error_type"`` or ``"fix_strategy"``).

        Returns:
            A list of ``(value, count)`` tuples sorted by descending
            count.
        """
        with self._lock:
            counts: dict[str, int] = {}
            for entry in self._entries:
                value = getattr(entry, field_name, "")
                counts[value] = counts.get(value, 0) + 1
            return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))

    # ------------------------------------------------------------------
    # Dict / JSON summary
    # ------------------------------------------------------------------
    def summary(self) -> dict[str, Any]:
        """Return a summary dict of the report.

        Includes aggregate metrics (risk level, success rate, average
        retries) alongside the raw entries, so JSON/programmatic consumers
        get the same enriched view as the Markdown export.
        """
        with self._lock:
            resolved_count = sum(1 for e in self._entries if e.resolved)
            return {
                "report_id": self._report_id,
                "bug_count": self.bug_count,
                "resolved": resolved_count,
                "unresolved": self.bug_count - resolved_count,
                "success_rate": round(self.success_rate, 2),
                "average_retries": round(self.average_retries, 2),
                "risk_level": self.risk_level,
                "tokens": self._total_tokens,
                "duration": round(self.duration_seconds, 2),
                "entries": [
                    {
                        "error_type": e.error_type,
                        "location": e.location,
                        "explanation": e.explanation,
                        "fix_strategy": e.fix_strategy,
                        "fix_description": e.fix_description,
                        "retry_count": e.retry_count,
                        "resolved": e.resolved,
                        "timestamp": e.timestamp,
                    }
                    for e in self._entries
                ],
            }

    def clear(self) -> None:
        """Clear all entries and reset the report."""
        with self._lock:
            self._entries = []
            self._total_tokens = 0
            self._start_time = datetime.now()
            self._report_id = (
                f"STEADY-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            )

    @property
    def entries(self) -> list[BugEntry]:
        """The list of recorded :class:`BugEntry` objects."""
        with self._lock:
            return list(self._entries)

    @property
    def bug_count(self) -> int:
        """Total number of bugs recorded."""
        with self._lock:
            return len(self._entries)

    @property
    def duration_seconds(self) -> float:
        """Seconds elapsed since the report started."""
        with self._lock:
            return (datetime.now() - self._start_time).total_seconds()
