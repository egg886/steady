"""Bug Tour Report module for steady.

Uses the 'tour guide / scenic spot / ticket' metaphor:
    - report_id  = ticket (your entry to the bug tour)
    - bugs       = scenic spots (each bug is a stop on the tour)
    - fixes      = tour commentary (what went wrong and how we fixed it)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Union


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
    """

    def __init__(self) -> None:
        self._entries: list[BugEntry] = []
        self._start_time: datetime = datetime.now()
        self._total_tokens: int = 0
        self._report_id: str = f"STEADY-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    def add_entry(self, entry: BugEntry) -> None:
        """Add a bug entry to the report."""
        self._entries.append(entry)

    def add_tokens(self, count: int) -> None:
        """Record LLM tokens used."""
        self._total_tokens += count

    def export(
        self, format: Literal["markdown", "json", "dict"] = "markdown"
    ) -> Union[str, dict]:
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

        # markdown format
        lines: list[str] = []
        lines.append(f"# Bug Tour Report")
        lines.append(f"")
        lines.append(f"**Ticket ID:** `{self._report_id}`")
        lines.append(f"**Duration:** {self.duration_seconds:.2f}s")
        lines.append(f"**Scenic Spots (bugs):** {self.bug_count}")
        resolved_count = sum(1 for e in self._entries if e.resolved)
        lines.append(f"**Resolved:** {resolved_count} / {self.bug_count}")
        if self._total_tokens > 0:
            lines.append(f"**LLM Tokens Used:** {self._total_tokens}")
        lines.append(f"")

        if not self._entries:
            lines.append("*No bugs encountered. The tour was uneventful.*")
        else:
            lines.append("## Tour Stops")
            lines.append("")
            for i, entry in enumerate(self._entries, 1):
                status = "resolved" if entry.resolved else "unresolved"
                lines.append(f"### Stop {i}: {entry.error_type}")
                lines.append(f"")
                lines.append(f"- **Location:** {entry.location}")
                lines.append(f"- **What happened:** {entry.explanation}")
                lines.append(f"- **Fix strategy:** `{entry.fix_strategy}`")
                lines.append(f"- **Tour commentary:** {entry.fix_description}")
                lines.append(f"- **Retries:** {entry.retry_count}")
                lines.append(f"- **Status:** {status}")
                lines.append(f"- **Timestamp:** {entry.timestamp}")
                lines.append(f"")

        return "\n".join(lines)

    def summary(self) -> dict:
        """Return a summary dict of the report."""
        resolved_count = sum(1 for e in self._entries if e.resolved)
        return {
            "report_id": self._report_id,
            "bug_count": self.bug_count,
            "resolved": resolved_count,
            "unresolved": self.bug_count - resolved_count,
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
        self._entries = []
        self._total_tokens = 0
        self._start_time = datetime.now()
        self._report_id = f"STEADY-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    @property
    def entries(self) -> list[BugEntry]:
        return self._entries

    @property
    def bug_count(self) -> int:
        return len(self._entries)

    @property
    def duration_seconds(self) -> float:
        return (datetime.now() - self._start_time).total_seconds()
