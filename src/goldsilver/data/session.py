from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo


STOCKHOLM = ZoneInfo("Europe/Stockholm")


def stockholm_now() -> datetime:
    return datetime.now(STOCKHOLM)


def stockholm_date_of(ts_utc: datetime) -> date:
    return ts_utc.astimezone(STOCKHOLM).date()


def stockholm_midnight_utc(for_date: date | None = None) -> datetime:
    if for_date is None:
        for_date = stockholm_now().date()
    midnight_local = datetime(
        for_date.year, for_date.month, for_date.day, tzinfo=STOCKHOLM
    )
    return midnight_local.astimezone(timezone.utc)
