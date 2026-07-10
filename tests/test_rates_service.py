"""Tests for RateService — USA (FRED DFF) and Sweden (Riksbank) policy rate polling."""

from __future__ import annotations

from datetime import date

import pytest

from goldsilver.data import rates_service
from goldsilver.data.fred import FredObservation
from goldsilver.data.models_macro import RatePoint
from goldsilver.data.rates_service import RateService
from goldsilver.data.riksbank_client import RiksbankObservation


@pytest.mark.asyncio
async def test_fed_refresh_emits_rate_point(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rates_service, "fred_api_key", lambda: "test-key")

    async def fake_fetch(series_id: str, *, api_key: str) -> FredObservation:
        assert series_id == "DFF"
        assert api_key == "test-key"
        return FredObservation(value=5.33, previous=5.08, asof=date(2026, 6, 9))

    monkeypatch.setattr(rates_service, "fetch_fred_pair", fake_fetch)

    emitted: list[RatePoint | None] = []
    service = RateService("fed", handler=emitted.append)

    await service.refresh_now()

    assert len(emitted) == 1
    point = emitted[0]
    assert point is not None
    assert point.source == "fed"
    assert point.value == 5.33
    assert point.previous == 5.08


@pytest.mark.asyncio
async def test_fed_refresh_without_key_emits_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rates_service, "fred_api_key", lambda: "")

    emitted: list[RatePoint | None] = []
    service = RateService("fed", handler=emitted.append)

    await service.refresh_now()

    assert emitted == [None]


@pytest.mark.asyncio
async def test_riksbank_refresh_emits_rate_point(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_fetch() -> RiksbankObservation:
        return RiksbankObservation(value=1.75, previous=2.0, asof=date(2026, 7, 10))

    monkeypatch.setattr(rates_service, "fetch_policy_rate", fake_fetch)

    emitted: list[RatePoint | None] = []
    service = RateService("riksbank", handler=emitted.append)

    await service.refresh_now()

    assert len(emitted) == 1
    point = emitted[0]
    assert point is not None
    assert point.source == "riksbank"
    assert point.value == 1.75
    assert point.previous == 2.0


@pytest.mark.asyncio
async def test_riksbank_refresh_failure_emits_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_fetch() -> None:
        return None

    monkeypatch.setattr(rates_service, "fetch_policy_rate", fake_fetch)

    emitted: list[RatePoint | None] = []
    service = RateService("riksbank", handler=emitted.append)

    await service.refresh_now()

    assert emitted == []
