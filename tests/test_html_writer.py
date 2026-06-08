"""Tests for report file writing, the HTML guard, sidecars, and index generation."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from goldsilver.data.session import STOCKHOLM
from goldsilver.reports.html_writer import is_valid_html, write_index, write_report
from goldsilver.reports.models import ReportRun, ReportStatus, Verdict

_VERDICT = Verdict(
    intraday="BUY",
    swing="HOLD",
    confidence=80,
    swedish_phase="US_INFLUENCE",
    us_state="OPEN",
    usd_impact="Neutral",
    gold_impact="Positive",
    news_impact="Neutral",
    geopolitical_impact="Neutral",
    top_reasons=["a", "b", "c"],
    what_would_change=["x"],
)


def _run(
    symbol: str,
    *,
    hour: int = 14,
    minute: int = 0,
    day: int = 8,
    status: ReportStatus = ReportStatus.SUCCESS,
    verdict: Verdict | None = None,
) -> ReportRun:
    return ReportRun(
        ticker=symbol,
        label=symbol,
        kind="stock",
        started_at=datetime(2026, 6, day, hour, minute, tzinfo=STOCKHOLM),
        status=status,
        verdict=verdict,
    )


def test_is_valid_html() -> None:
    assert is_valid_html("<!doctype html><html></html>")
    assert is_valid_html("  <HTML>x</HTML>")
    assert not is_valid_html("```html\njunk")
    assert not is_valid_html(None)
    assert not is_valid_html("")


def test_write_success_path_and_sidecar(tmp_path: Path) -> None:
    run = _run("XAU", verdict=_VERDICT)
    out = write_report(tmp_path, run, "<!doctype html><html><body>ok</body></html>")
    assert out.status is ReportStatus.SUCCESS
    assert out.html_path == "2026-06-08/14-00-XAU.html"
    html_file = tmp_path / "2026-06-08" / "14-00-XAU.html"
    json_file = tmp_path / "2026-06-08" / "14-00-XAU.json"
    assert html_file.read_text("utf-8").startswith("<!doctype html>")
    assert '"ticker":"XAU"' in json_file.read_text("utf-8").replace(" ", "")


def test_safe_name_in_path(tmp_path: Path) -> None:
    run = _run("LUG.ST")
    out = write_report(tmp_path, run, "<!doctype html><html>x</html>")
    assert out.html_path == "2026-06-08/14-00-LUG-ST.html"
    assert (tmp_path / "2026-06-08" / "14-00-LUG-ST.html").exists()


def test_malformed_downgrade(tmp_path: Path) -> None:
    run = _run("XAG")
    out = write_report(tmp_path, run, "I forgot to output HTML")
    assert out.status is ReportStatus.MALFORMED
    body = (tmp_path / out.html_path).read_text("utf-8")
    assert "Report problem" in body
    assert "I forgot to output HTML" in body


def test_failure_status_writes_error_shell(tmp_path: Path) -> None:
    run = _run("NVDA", status=ReportStatus.TIMEOUT)
    run.error = "timed out after 180s"
    out = write_report(tmp_path, run, None)
    assert out.status is ReportStatus.TIMEOUT
    body = (tmp_path / out.html_path).read_text("utf-8")
    assert "TIMEOUT" in body


def test_index_grouping_and_order(tmp_path: Path) -> None:
    write_report(
        tmp_path, _run("XAU", day=8, verdict=_VERDICT), "<!doctype html><html>g</html>"
    )
    write_report(tmp_path, _run("XAG", day=9), "<!doctype html><html>s</html>")
    index = write_index(tmp_path)
    text = index.read_text("utf-8")
    assert text.index("2026-06-09") < text.index("2026-06-08")  # newest first
    assert "14-00-XAU.html" in text
    assert "BUY 80%" in text  # verdict badge
    assert "—" in text  # XAG run has no verdict


def test_index_empty_state(tmp_path: Path) -> None:
    index = write_index(tmp_path)
    assert "No reports generated yet" in index.read_text("utf-8")
