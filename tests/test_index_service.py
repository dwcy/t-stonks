"""Tests for IndexService — DAX/CAC 40/FTSE 100/Nikkei 225 session detection + parsing."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from goldsilver.data import index_service
from goldsilver.data.index_service import (
    INDEX_DEFINITIONS,
    IndexService,
    _is_session_open,
)
from goldsilver.data.models_macro import IndexPoint


def test_all_four_exchanges_are_defined() -> None:
    assert set(INDEX_DEFINITIONS) == {"DAX", "CAC40", "FTSE100", "NIKKEI225"}
    assert INDEX_DEFINITIONS["DAX"].yf_symbol == "^GDAXI"
    assert INDEX_DEFINITIONS["CAC40"].yf_symbol == "^FCHI"
    assert INDEX_DEFINITIONS["FTSE100"].yf_symbol == "^FTSE"
    assert INDEX_DEFINITIONS["NIKKEI225"].yf_symbol == "^N225"


def test_session_open_during_frankfurt_trading_hours() -> None:
    definition = INDEX_DEFINITIONS["DAX"]
    # Tuesday 10:00 Europe/Berlin
    tuesday_10am_berlin = datetime(2026, 6, 9, 8, 0, tzinfo=timezone.utc)
    assert _is_session_open(definition, tuesday_10am_berlin) is True


def test_session_closed_outside_trading_hours() -> None:
    definition = INDEX_DEFINITIONS["DAX"]
    tuesday_midnight_utc = datetime(2026, 6, 9, 23, 0, tzinfo=timezone.utc)
    assert _is_session_open(definition, tuesday_midnight_utc) is False


def test_session_closed_on_weekend() -> None:
    definition = INDEX_DEFINITIONS["FTSE100"]
    saturday_noon_utc = datetime(2026, 6, 13, 12, 0, tzinfo=timezone.utc)
    assert _is_session_open(definition, saturday_noon_utc) is False


def test_tokyo_session_uses_its_own_timezone() -> None:
    definition = INDEX_DEFINITIONS["NIKKEI225"]
    # 01:00 UTC == 10:00 Asia/Tokyo on a weekday
    weekday_10am_tokyo = datetime(2026, 6, 9, 1, 0, tzinfo=timezone.utc)
    assert _is_session_open(definition, weekday_10am_tokyo) is True
    assert weekday_10am_tokyo.astimezone(ZoneInfo("Asia/Tokyo")).hour == 10


@pytest.mark.asyncio
async def test_refresh_emits_index_point(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_pair(yf_symbol: str):
        assert yf_symbol == "^GDAXI"
        return (24000.0, 23800.0, datetime(2026, 6, 9, 16, 0, tzinfo=timezone.utc))

    monkeypatch.setattr(index_service, "fetch_daily_close_pair", fake_pair)

    emitted: list[IndexPoint] = []
    service = IndexService("DAX", handler=emitted.append)

    await service.refresh_now()

    assert len(emitted) == 1
    assert emitted[0].symbol == "DAX"
    assert emitted[0].level == 24000.0
    assert emitted[0].previous_close == 23800.0


@pytest.mark.asyncio
async def test_refresh_failure_emits_stale(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_pair(yf_symbol: str):
        return None

    monkeypatch.setattr(index_service, "fetch_daily_close_pair", fake_pair)

    stale_calls: list[str] = []

    async def stale_handler(symbol: str, since) -> None:
        stale_calls.append(symbol)

    service = IndexService("FTSE100", stale_handler=stale_handler)

    await service.refresh_now()

    assert stale_calls == ["FTSE100"]
