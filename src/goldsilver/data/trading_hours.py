"""Stockholm trading-hours gate (08:00–22:54)."""

from __future__ import annotations

from datetime import date, datetime

from goldsilver.data.session import STOCKHOLM


OPEN_HOUR = 8
CLOSE_HOUR = 22
CLOSE_MINUTE = 54


def to_local(ts_utc: datetime) -> datetime:
    return ts_utc.astimezone(STOCKHOLM)


def is_open(now_local: datetime) -> bool:
    if now_local.hour < OPEN_HOUR:
        return False
    if now_local.hour > CLOSE_HOUR:
        return False
    if now_local.hour == CLOSE_HOUR and now_local.minute >= CLOSE_MINUTE:
        return False
    return True


def trading_day_of(now_local: datetime) -> date:
    return now_local.date()
