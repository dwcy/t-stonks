"""Tests for ReportController's chart-modal lookup helpers (watchlist, latest run, next run)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from goldsilver.data.session import STOCKHOLM
from goldsilver.data.settings import ReportSettings
from goldsilver.report_controller import ReportController
from goldsilver.reports.models import ReportRun, ReportStatus


class _StubApp:
    def __init__(self, report: ReportSettings) -> None:
        self._settings = SimpleNamespace(report=report)


def _controller(tmp_path: Path, **report_overrides: object) -> ReportController:
    # out_dir is absolute, so ReportService.out_root() (Path.cwd() / out_dir)
    # resolves to tmp_path regardless of the real working directory.
    report = ReportSettings(
        report_tickers=["NVDA"], out_dir=str(tmp_path), **report_overrides
    )
    return ReportController(_StubApp(report))  # type: ignore[arg-type]


def test_is_watchlisted_true_for_pinned_and_added_tickers(tmp_path: Path) -> None:
    controller = _controller(tmp_path)

    assert controller.is_watchlisted("XAU") is True
    assert controller.is_watchlisted("NVDA") is True
    assert controller.is_watchlisted("AAPL") is False


def test_is_watchlisted_false_when_excluded(tmp_path: Path) -> None:
    controller = _controller(tmp_path, report_excluded=["NVDA"])

    assert controller.is_watchlisted("NVDA") is False


def test_latest_run_for_returns_most_recent(tmp_path: Path) -> None:
    controller = _controller(tmp_path)
    old = ReportRun(
        ticker="NVDA",
        label="NVDA",
        kind="stock",
        started_at=datetime(2026, 6, 1, 9, 0, tzinfo=STOCKHOLM),
        status=ReportStatus.SUCCESS,
    )
    new = ReportRun(
        ticker="NVDA",
        label="NVDA",
        kind="stock",
        started_at=datetime(2026, 6, 2, 9, 0, tzinfo=STOCKHOLM),
        status=ReportStatus.SUCCESS,
        html_path="2026-06-02/09-00-NVDA.html",
    )
    controller._runs = [new, old]

    assert controller.latest_run_for("NVDA") is new
    assert controller.latest_run_for("AAPL") is None


def test_latest_report_summary_and_uri(tmp_path: Path) -> None:
    controller = _controller(tmp_path)
    run = ReportRun(
        ticker="NVDA",
        label="NVDA",
        kind="stock",
        started_at=datetime(2026, 6, 2, 9, 0, tzinfo=STOCKHOLM),
        status=ReportStatus.SUCCESS,
        html_path="2026-06-02/09-00-NVDA.html",
    )
    controller._runs = [run]
    (tmp_path / "2026-06-02").mkdir()
    (tmp_path / "2026-06-02" / "09-00-NVDA.html").write_text("<html></html>")

    summary = controller.latest_report_summary_for("NVDA")
    uri = controller.latest_report_uri_for("NVDA")

    assert summary is not None and "SUCCESS" in summary
    assert uri is not None and uri.startswith("file:")
    assert controller.latest_report_summary_for("AAPL") is None
    assert controller.latest_report_uri_for("AAPL") is None


def test_next_run_at_none_when_disabled(tmp_path: Path) -> None:
    controller = _controller(tmp_path, enabled=False)

    assert controller.next_run_at() is None


def test_next_run_at_returns_future_time_when_enabled(tmp_path: Path) -> None:
    controller = _controller(tmp_path, enabled=True, interval_minutes=60)

    next_at = controller.next_run_at()

    assert next_at is not None
