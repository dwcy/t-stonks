"""Europe/Stockholm session helpers — thin wrappers over marketcore.session."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from marketcore import session as _session

STOCKHOLM = ZoneInfo("Europe/Stockholm")


def stockholm_now() -> datetime:
    return _session.now(STOCKHOLM)


def stockholm_date_of(ts_utc: datetime) -> date:
    return _session.date_of(ts_utc, STOCKHOLM)


def stockholm_midnight_utc(for_date: date | None = None) -> datetime:
    return _session.midnight_utc(STOCKHOLM, for_date)
