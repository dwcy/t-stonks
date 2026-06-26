"""Timezone-aware now/date/midnight helpers, parameterized by ZoneInfo."""

from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo


def now(tz: ZoneInfo) -> datetime:
    return datetime.now(tz)


def date_of(ts_utc: datetime, tz: ZoneInfo) -> date:
    return ts_utc.astimezone(tz).date()


def midnight_utc(tz: ZoneInfo, for_date: date | None = None) -> datetime:
    if for_date is None:
        for_date = now(tz).date()
    midnight_local = datetime(for_date.year, for_date.month, for_date.day, tzinfo=tz)
    return midnight_local.astimezone(timezone.utc)
