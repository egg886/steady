"""Tests for the Bug Tour Report module."""

from __future__ import annotations

import json
import time

import pytest

from steady.report import BugEntry, BugReport


# ---------------------------------------------------------------------- #
# Fixtures
# ---------------------------------------------------------------------- #
def _make_entry(
    *,
    error_type: str = "ZeroDivisionError",
    location: str = "file.py:2 in f",
    explanation: str = "division by zero",
    fix_strategy: str = "ast_repair",
    fix_description: str = "Removed error-causing statement",
    retry_count: int = 1,
    resolved: bool = True,
) -> BugEntry:
    """Build a BugEntry with sensible defaults."""
    return BugEntry(
        error_type=error_type,
        location=location,
        explanation=explanation,
        fix_strategy=fix_strategy,
        fix_description=fix_description,
        retry_count=retry_count,
        resolved=resolved,
    )


@pytest.fixture
def report():
    """Provide a fresh BugReport."""
    return BugReport()


# ---------------------------------------------------------------------- #
# add_entry / entries
# ---------------------------------------------------------------------- #
def test_add_entry(report):
    """add_entry should append a BugEntry and bump the bug count."""
    assert report.bug_count == 0
    entry = _make_entry()
    report.add_entry(entry)
    assert report.bug_count == 1
    assert report.entries[0] is entry


# ---------------------------------------------------------------------- #
# add_tokens
# ---------------------------------------------------------------------- #
def test_add_tokens(report):
    """add_tokens should accumulate token counts."""
    report.add_tokens(50)
    report.add_tokens(30)
    assert report.summary()["tokens"] == 80


# ---------------------------------------------------------------------- #
# export formats
# ---------------------------------------------------------------------- #
def test_export_markdown(report):
    """export('markdown') should return a markdown string describing the tour."""
    report.add_entry(_make_entry(resolved=True))
    md = report.export("markdown")
    assert isinstance(md, str)
    assert "Bug Tour Report" in md
    assert "Ticket ID" in md
    assert "ZeroDivisionError" in md
    assert "resolved" in md


def test_export_json(report):
    """export('json') should return valid JSON with the expected structure."""
    report.add_entry(_make_entry())
    js = report.export("json")
    assert isinstance(js, str)
    data = json.loads(js)
    assert data["bug_count"] == 1
    assert data["resolved"] == 1
    assert len(data["entries"]) == 1
    assert data["entries"][0]["error_type"] == "ZeroDivisionError"


def test_export_dict(report):
    """export('dict') should return a plain dict (the summary)."""
    report.add_entry(_make_entry())
    d = report.export("dict")
    assert isinstance(d, dict)
    assert d["bug_count"] == 1
    assert "entries" in d
    assert isinstance(d["entries"], list)


# ---------------------------------------------------------------------- #
# clear
# ---------------------------------------------------------------------- #
def test_clear(report):
    """clear() should remove all entries and reset the token counter."""
    report.add_entry(_make_entry())
    report.add_tokens(100)
    assert report.bug_count == 1

    report.clear()
    assert report.bug_count == 0
    assert report.entries == []
    assert report.summary()["tokens"] == 0


# ---------------------------------------------------------------------- #
# summary
# ---------------------------------------------------------------------- #
def test_summary(report):
    """summary() should report resolved/unresolved counts and entry details."""
    report.add_entry(_make_entry(resolved=True))
    report.add_entry(
        _make_entry(
            error_type="NameError",
            location="file.py:3 in g",
            fix_strategy="failed",
            resolved=False,
            retry_count=2,
        )
    )
    s = report.summary()
    assert s["bug_count"] == 2
    assert s["resolved"] == 1
    assert s["unresolved"] == 1
    assert len(s["entries"]) == 2
    assert s["entries"][0]["resolved"] is True
    assert s["entries"][1]["resolved"] is False


# ---------------------------------------------------------------------- #
# bug_count
# ---------------------------------------------------------------------- #
def test_bug_count(report):
    """bug_count should reflect the number of recorded entries."""
    assert report.bug_count == 0
    report.add_entry(_make_entry())
    assert report.bug_count == 1
    report.add_entry(_make_entry())
    assert report.bug_count == 2
    report.clear()
    assert report.bug_count == 0


# ---------------------------------------------------------------------- #
# duration_seconds
# ---------------------------------------------------------------------- #
def test_duration_seconds(report):
    """duration_seconds should be a non-negative float that grows over time."""
    duration = report.duration_seconds
    assert isinstance(duration, float)
    assert duration >= 0

    time.sleep(0.01)
    assert report.duration_seconds >= duration
