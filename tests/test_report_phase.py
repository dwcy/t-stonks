"""Unit tests for Swedish session phase + US market state derivation."""

from __future__ import annotations

from datetime import datetime

import pytest

from goldsilver.data.session import STOCKHOLM
from goldsilver.reports.constants import safe_name
from goldsilver.reports.models import SwedishPhase, USMarketState
from goldsilver.reports.phase import swedish_phase, us_market_state


def _sthlm(h: int, m: int = 0, *, day: int = 8, month: int = 6) -> datetime:
    return datetime(2026, month, day, h, m, tzinfo=STOCKHOLM)


@pytest.mark.parametrize(
    ("hour", "minute", "expected"),
    [
        (8, 30, SwedishPhase.CLOSED),
        (9, 0, SwedishPhase.MORNING_STRENGTH),
        (9, 59, SwedishPhase.MORNING_STRENGTH),
        (10, 0, SwedishPhase.MIDDAY_WEAKNESS),
        (11, 59, SwedishPhase.MIDDAY_WEAKNESS),
        (12, 0, SwedishPhase.TREND_FOLLOWING),
        (14, 29, SwedishPhase.TREND_FOLLOWING),
        (14, 30, SwedishPhase.US_INFLUENCE),
        (17, 29, SwedishPhase.US_INFLUENCE),
        (17, 30, SwedishPhase.US_DOMINATED),
        (22, 53, SwedishPhase.US_DOMINATED),
        (22, 54, SwedishPhase.CLOSED),
        (23, 30, SwedishPhase.CLOSED),
    ],
)
def test_swedish_phase_bands(hour: int, minute: int, expected: SwedishPhase) -> None:
    assert swedish_phase(_sthlm(hour, minute)) == expected


@pytest.mark.parametrize(
    ("hour", "minute", "expected"),
    [
        # Summer: Stockholm (CEST, UTC+2) is ET (EDT, UTC-4) + 6h.
        (9, 30, USMarketState.CLOSED),  # 03:30 ET overnight
        (14, 30, USMarketState.PRE_MARKET),  # 08:30 ET
        (15, 35, USMarketState.OPENING),  # 09:35 ET
        (16, 30, USMarketState.OPEN),  # 10:30 ET
        (21, 40, USMarketState.NEAR_CLOSE),  # 15:40 ET
        (22, 30, USMarketState.CLOSED),  # 16:30 ET after close
    ],
)
def test_us_market_state_summer(
    hour: int, minute: int, expected: USMarketState
) -> None:
    assert us_market_state(_sthlm(hour, minute)) == expected


def test_us_state_dst_misalignment_january() -> None:
    # In January both are on standard time: Stockholm (CET, UTC+1) is ET (EST, UTC-5) + 6h.
    # 15:35 Stockholm -> 09:35 ET -> OPENING. Deriving from a real ET conversion keeps this exact.
    dt = _sthlm(15, 35, day=8, month=1)
    assert us_market_state(dt) == USMarketState.OPENING


def test_us_state_weekend_closed() -> None:
    # 2026-06-13 is a Saturday.
    assert us_market_state(_sthlm(16, 30, day=13)) == USMarketState.CLOSED


def test_safe_name() -> None:
    assert safe_name("XAU") == "XAU"
    assert safe_name("LUG.ST") == "LUG-ST"
    assert safe_name("BRK.B") == "BRK-B"
    assert safe_name("VOLV-B.ST") == "VOLV-B-ST"
