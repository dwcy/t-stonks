"""Tests for the pre-open futures models, registry, and Terminer strip rendering."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from textual.app import App, ComposeResult

from goldsilver.data.futures_service import _REGISTRY
from goldsilver.data.models_futures import FuturesSnapshot, FutureQuote
from goldsilver.widgets.futures_strip import FuturesStrip


def _quote(
    label: str, kind: str, price: float, prev: float, *, live: bool
) -> FutureQuote:
    market = "US" if live else "EU"
    return FutureQuote(
        symbol=f"{label}=F",
        label=label,
        market=market,
        kind=kind,
        price=price,
        previous_close=prev,
        is_live=live,
        time=datetime.now(timezone.utc),
    )


class _Harness(App[None]):
    def compose(self) -> ComposeResult:
        yield FuturesStrip()


def test_change_percent_is_relative_to_previous_close() -> None:
    quote = _quote("S&P", "index_future", 101.0, 100.0, live=True)

    assert quote.change_percent == pytest.approx(1.0)


def test_eu_registry_entries_are_not_live() -> None:
    eu = [row for row in _REGISTRY if row[2] in ("SE", "EU")]

    assert eu and all(is_live is False for *_, is_live in eu)


def test_us_registry_entries_are_live() -> None:
    us = [row for row in _REGISTRY if row[2] == "US"]

    assert us and all(is_live is True for *_, is_live in us)


@pytest.mark.asyncio
async def test_cash_quotes_render_under_a_labeled_group() -> None:
    snapshot = FuturesSnapshot(
        quotes=(
            _quote("S&P", "index_future", 101.0, 100.0, live=True),
            _quote("OMXS30", "cash_index", 99.0, 100.0, live=False),
        ),
        fetched_at=datetime.now(timezone.utc),
    )

    app = _Harness()
    async with app.run_test() as pilot:
        strip = app.query_one(FuturesStrip)
        strip.apply_snapshot(snapshot)
        await pilot.pause()
        plain = str(strip.render())

    assert "S&P" in plain.split("cash(igår)")[0]
    assert "OMXS30" in plain.split("cash(igår)")[1]


@pytest.mark.asyncio
async def test_rate_and_vol_render_levels_not_percent_change() -> None:
    snapshot = FuturesSnapshot(
        quotes=(
            _quote("US10Y", "rate", 4.53, 4.55, live=True),
            _quote("VIX", "vol", 20.99, 19.0, live=True),
        ),
        fetched_at=datetime.now(timezone.utc),
    )

    app = _Harness()
    async with app.run_test() as pilot:
        strip = app.query_one(FuturesStrip)
        strip.apply_snapshot(snapshot)
        await pilot.pause()
        plain = str(strip.render())

    assert "4.53%" in plain and "20.99" in plain
