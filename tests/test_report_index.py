"""Tests for index.html badge rendering across verdict, null, and failure states."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from goldsilver.data.session import STOCKHOLM
from goldsilver.reports.html_writer import write_index, write_report
from goldsilver.reports.models import ReportRun, ReportStatus, Verdict

_VERDICT = Verdict(
    intraday="SELL",
    swing="SELL",
    confidence=63,
    swedish_phase="US_DOMINATED",
    us_state="OPEN",
    usd_impact="Negative",
    gold_impact="Negative",
    news_impact="Negative",
    geopolitical_impact="Neutral",
    top_reasons=["a", "b", "c"],
    what_would_change=["z"],
)


def _run(
    symbol: str, minute: int, status: ReportStatus, verdict: Verdict | None
) -> ReportRun:
    return ReportRun(
        ticker=symbol,
        label=symbol,
        kind="stock",
        started_at=datetime(2026, 6, 8, 16, minute, tzinfo=STOCKHOLM),
        status=status,
        verdict=verdict,
    )


def test_index_shows_verdict_confidence_and_failure_badge(tmp_path: Path) -> None:
    write_report(
        tmp_path,
        _run("XAU", 0, ReportStatus.SUCCESS, _VERDICT),
        "<!doctype html><html>g</html>",
    )
    fail = _run("NVDA", 1, ReportStatus.TIMEOUT, None)
    fail.error = "timed out"
    write_report(tmp_path, fail, None)

    text = write_index(tmp_path).read_text("utf-8")

    assert "SELL 63%" in text
    assert "TIMEOUT" in text  # failure badge
    assert "16-00-XAU.html" in text
    assert "16-01-NVDA.html" in text


def test_index_newest_time_first_within_day(tmp_path: Path) -> None:
    write_report(
        tmp_path,
        _run("XAU", 5, ReportStatus.SUCCESS, None),
        "<!doctype html><html>a</html>",
    )
    write_report(
        tmp_path,
        _run("XAG", 35, ReportStatus.SUCCESS, None),
        "<!doctype html><html>b</html>",
    )

    text = write_index(tmp_path).read_text("utf-8")

    assert text.index("16-35-XAG.html") < text.index("16-05-XAU.html")
