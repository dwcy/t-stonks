"""Pure clock logic: derive Swedish session phase and US-market state from a datetime."""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

from goldsilver.data.session import STOCKHOLM
from goldsilver.reports.models import SwedishPhase, USMarketState

NEW_YORK = ZoneInfo("America/New_York")

# US cash-session edges in Eastern time (DST handled by converting to NEW_YORK).
_US_PREMARKET_OPEN = time(8, 0)
_US_OPEN = time(9, 30)
_US_OPENING_END = time(9, 45)
_US_NEAR_CLOSE = time(15, 30)
_US_CLOSE = time(16, 0)


def swedish_phase(now_local: datetime) -> SwedishPhase:
    """Map a Europe/Stockholm-aware datetime to a session phase label."""
    local = now_local.astimezone(STOCKHOLM)
    minutes = local.hour * 60 + local.minute
    if minutes < 9 * 60 or minutes >= 22 * 60 + 54:
        return SwedishPhase.CLOSED
    if minutes < 10 * 60:
        return SwedishPhase.MORNING_STRENGTH
    if minutes < 12 * 60:
        return SwedishPhase.MIDDAY_WEAKNESS
    if minutes < 14 * 60 + 30:
        return SwedishPhase.TREND_FOLLOWING
    if minutes < 17 * 60 + 30:
        return SwedishPhase.US_INFLUENCE
    return SwedishPhase.US_DOMINATED


def us_market_state(now_local: datetime) -> USMarketState:
    """Infer US cash-market state by converting the instant to Eastern time."""
    et = now_local.astimezone(NEW_YORK)
    if et.weekday() >= 5:
        return USMarketState.CLOSED
    t = et.timetz().replace(tzinfo=None)
    if t < _US_PREMARKET_OPEN:
        return USMarketState.CLOSED
    if t < _US_OPEN:
        return USMarketState.PRE_MARKET
    if t < _US_OPENING_END:
        return USMarketState.OPENING
    if t < _US_NEAR_CLOSE:
        return USMarketState.OPEN
    if t < _US_CLOSE:
        return USMarketState.NEAR_CLOSE
    return USMarketState.CLOSED
