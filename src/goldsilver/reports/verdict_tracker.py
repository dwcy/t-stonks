"""Score past report verdicts against the subsequent 1-day and 1-week price moves."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import yfinance as yf

from goldsilver.reports.models import ReportRun, ReportTicker
from goldsilver.reports.reference_quote import quote_symbol

# A HOLD counts as right when the move stays inside this band.
HOLD_BAND_PCT = 1.0


@dataclass(slots=True)
class TickerAccuracy:
    ticker: str
    intraday_hits: int = 0
    intraday_n: int = 0
    swing_hits: int = 0
    swing_n: int = 0


def yf_symbol_for_run(run: ReportRun) -> str:
    if run.kind == "metal":
        ticker = ReportTicker.metal(run.ticker)
    elif run.kind == "commodity":
        ticker = ReportTicker.commodity(run.ticker)
    else:
        ticker = ReportTicker.stock(run.ticker)
    return quote_symbol(ticker)


def _direction_correct(call: str, move_pct: float) -> bool:
    if call == "BUY":
        return move_pct > 0.0
    if call == "SELL":
        return move_pct < 0.0
    return abs(move_pct) <= HOLD_BAND_PCT


def _close_on_or_before(closes: dict[date, float], target: date) -> float | None:
    earlier = [d for d in closes if d <= target]
    return closes[max(earlier)] if earlier else None


def _close_after(closes: dict[date, float], target: date) -> float | None:
    later = [d for d in closes if d > target]
    return closes[min(later)] if later else None


def _close_on_or_after(closes: dict[date, float], target: date) -> float | None:
    later = [d for d in closes if d >= target]
    return closes[min(later)] if later else None


def evaluate_accuracy(
    runs: list[ReportRun], closes_by_ticker: dict[str, dict[date, float]]
) -> list[TickerAccuracy]:
    per: dict[str, TickerAccuracy] = {}
    for run in runs:
        if run.verdict is None:
            continue
        closes = closes_by_ticker.get(run.ticker)
        if not closes:
            continue
        when = run.started_at.date()
        entry = _close_on_or_before(closes, when)
        if entry is None or entry <= 0:
            continue
        acc = per.setdefault(run.ticker, TickerAccuracy(ticker=run.ticker))
        day_close = _close_after(closes, when)
        if day_close is not None:
            move = (day_close - entry) / entry * 100.0
            acc.intraday_n += 1
            if _direction_correct(run.verdict.intraday, move):
                acc.intraday_hits += 1
        week_close = _close_on_or_after(closes, when + timedelta(days=7))
        if week_close is not None:
            move = (week_close - entry) / entry * 100.0
            acc.swing_n += 1
            if _direction_correct(run.verdict.swing, move):
                acc.swing_hits += 1
    return sorted(per.values(), key=lambda a: a.ticker)


def fetch_daily_closes(
    symbols: dict[str, str], start: date
) -> dict[str, dict[date, float]]:
    """Run-ticker → date → close, fetched per yfinance symbol. Blocking; run in a thread."""
    out: dict[str, dict[date, float]] = {}
    for run_ticker, yf_sym in symbols.items():
        try:
            df = yf.Ticker(yf_sym).history(
                start=start.isoformat(), interval="1d", auto_adjust=False
            )
        except Exception:
            continue
        if df is None or len(df) == 0:
            continue
        closes: dict[date, float] = {}
        for idx, value in df["Close"].items():
            if value != value:
                continue
            closes[idx.to_pydatetime().date()] = float(value)
        if closes:
            out[run_ticker] = closes
    return out
