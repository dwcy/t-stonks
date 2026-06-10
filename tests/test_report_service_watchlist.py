"""Tests for watchlist filtering: report_excluded controls the effective run set."""

from __future__ import annotations

from goldsilver.data.settings import ReportSettings
from goldsilver.reports.report_service import ReportService


def test_effective_watchlist_filters_excluded() -> None:
    settings = ReportSettings(
        report_tickers=["NVDA", "LUG.ST"],
        report_excluded=["XAG", "NVDA"],
    )
    service = ReportService(lambda: settings)

    symbols = [t.symbol for t in service.effective_watchlist()]

    assert symbols == ["XAU", "LUG.ST"]


def test_full_watchlist_ignores_exclusions() -> None:
    settings = ReportSettings(report_tickers=["NVDA"], report_excluded=["XAU", "NVDA"])
    service = ReportService(lambda: settings)

    symbols = [t.symbol for t in service.full_watchlist()]

    assert symbols == ["XAU", "XAG", "NVDA"]


def test_resolve_tickers_keeps_metal_kind_even_when_excluded() -> None:
    settings = ReportSettings(report_tickers=[], report_excluded=["XAU"])
    service = ReportService(lambda: settings)

    (ticker,) = service.resolve_tickers(["XAU"])

    assert ticker.kind == "metal"
    assert ticker.label == "Gold"
