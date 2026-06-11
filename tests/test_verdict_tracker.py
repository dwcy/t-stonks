"""Tests for scoring report verdicts against subsequent price moves."""

from __future__ import annotations

from datetime import date, datetime

from goldsilver.data.session import STOCKHOLM
from goldsilver.reports.models import ReportRun, ReportStatus, Verdict
from goldsilver.reports.verdict_tracker import evaluate_accuracy, yf_symbol_for_run


def _verdict(intraday: str, swing: str) -> Verdict:
    return Verdict(
        intraday=intraday,
        swing=swing,
        confidence=70,
        swedish_phase="US_INFLUENCE",
        us_state="OPEN",
        usd_impact="Neutral",
        gold_impact="Neutral",
        news_impact="Neutral",
        geopolitical_impact="Neutral",
        top_reasons=["a"],
        what_would_change=["b"],
    )


def _run(ticker: str, day: int, intraday: str, swing: str) -> ReportRun:
    return ReportRun(
        ticker=ticker,
        label=ticker,
        kind="stock",
        started_at=datetime(2026, 6, day, 14, 0, tzinfo=STOCKHOLM),
        status=ReportStatus.SUCCESS,
        verdict=_verdict(intraday, swing),
    )


def test_buy_scored_against_next_day_and_week() -> None:
    closes = {
        date(2026, 6, 1): 100.0,
        date(2026, 6, 2): 103.0,
        date(2026, 6, 8): 95.0,
    }

    rows = evaluate_accuracy([_run("LUG.ST", 1, "BUY", "BUY")], {"LUG.ST": closes})

    (acc,) = rows
    assert acc.intraday_hits == 1 and acc.intraday_n == 1  # +3% next day
    assert acc.swing_hits == 0 and acc.swing_n == 1  # -5% on the week


def test_hold_correct_inside_band_and_recent_run_unscored() -> None:
    closes = {
        date(2026, 6, 1): 100.0,
        date(2026, 6, 2): 100.5,
    }
    runs = [
        _run("NVDA", 1, "HOLD", "HOLD"),
        _run("NVDA", 2, "BUY", "BUY"),  # no later close → not scored
    ]

    rows = evaluate_accuracy(runs, {"NVDA": closes})

    (acc,) = rows
    assert acc.intraday_hits == 1 and acc.intraday_n == 1
    assert acc.swing_n == 0  # week-out close never exists


def test_metal_runs_map_to_futures_symbols() -> None:
    gold = ReportRun(
        ticker="XAU",
        label="Gold",
        kind="metal",
        started_at=datetime(2026, 6, 1, 14, 0, tzinfo=STOCKHOLM),
        status=ReportStatus.SUCCESS,
    )

    assert yf_symbol_for_run(gold) == "GC=F"
