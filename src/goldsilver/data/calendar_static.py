from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from goldsilver.data.models_macro import CalendarEvent


_ET = ZoneInfo("America/New_York")
_CET = ZoneInfo("Europe/Stockholm")


def _at_et(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=_ET)


def _at_cet(year: int, month: int, day: int, hour: int, minute: int) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=_CET)


FOMC_2026: tuple[CalendarEvent, ...] = (
    CalendarEvent(source="FED", title="FOMC statement", scheduled_time=_at_et(2026, 1, 28, 14, 0), importance="HIGH"),
    CalendarEvent(source="FED", title="FOMC press conference (Powell)", scheduled_time=_at_et(2026, 1, 28, 14, 30), importance="HIGH"),
    CalendarEvent(source="FED", title="FOMC statement + SEP", scheduled_time=_at_et(2026, 3, 18, 14, 0), importance="HIGH"),
    CalendarEvent(source="FED", title="FOMC press conference (Powell)", scheduled_time=_at_et(2026, 3, 18, 14, 30), importance="HIGH"),
    CalendarEvent(source="FED", title="FOMC statement", scheduled_time=_at_et(2026, 4, 29, 14, 0), importance="HIGH"),
    CalendarEvent(source="FED", title="FOMC press conference (Powell)", scheduled_time=_at_et(2026, 4, 29, 14, 30), importance="HIGH"),
    CalendarEvent(source="FED", title="FOMC statement + SEP", scheduled_time=_at_et(2026, 6, 17, 14, 0), importance="HIGH"),
    CalendarEvent(source="FED", title="FOMC press conference (Powell)", scheduled_time=_at_et(2026, 6, 17, 14, 30), importance="HIGH"),
    CalendarEvent(source="FED", title="FOMC statement", scheduled_time=_at_et(2026, 7, 29, 14, 0), importance="HIGH"),
    CalendarEvent(source="FED", title="FOMC press conference (Powell)", scheduled_time=_at_et(2026, 7, 29, 14, 30), importance="HIGH"),
    CalendarEvent(source="FED", title="FOMC statement + SEP", scheduled_time=_at_et(2026, 9, 16, 14, 0), importance="HIGH"),
    CalendarEvent(source="FED", title="FOMC press conference (Powell)", scheduled_time=_at_et(2026, 9, 16, 14, 30), importance="HIGH"),
    CalendarEvent(source="FED", title="FOMC statement", scheduled_time=_at_et(2026, 11, 4, 14, 0), importance="HIGH"),
    CalendarEvent(source="FED", title="FOMC press conference (Powell)", scheduled_time=_at_et(2026, 11, 4, 14, 30), importance="HIGH"),
    CalendarEvent(source="FED", title="FOMC statement + SEP", scheduled_time=_at_et(2026, 12, 16, 14, 0), importance="HIGH"),
    CalendarEvent(source="FED", title="FOMC press conference (Powell)", scheduled_time=_at_et(2026, 12, 16, 14, 30), importance="HIGH"),
)

US_RELEASES_2026: tuple[CalendarEvent, ...] = (
    CalendarEvent(source="FED", title="GDP Q1 (2nd estimate)", scheduled_time=_at_et(2026, 5, 28, 8, 30), importance="HIGH"),
    CalendarEvent(source="FED", title="Personal Income & Outlays / PCE (Apr)", scheduled_time=_at_et(2026, 5, 28, 8, 30), importance="HIGH"),
    CalendarEvent(source="FED", title="ISM Manufacturing PMI (May)", scheduled_time=_at_et(2026, 6, 1, 10, 0), importance="MED"),
    CalendarEvent(source="FED", title="ISM Services PMI (May)", scheduled_time=_at_et(2026, 6, 3, 10, 0), importance="MED"),
    CalendarEvent(source="FED", title="International Trade (Apr)", scheduled_time=_at_et(2026, 6, 9, 8, 30), importance="MED"),
    CalendarEvent(source="FED", title="CPI (May)", scheduled_time=_at_et(2026, 6, 10, 8, 30), importance="HIGH"),
    CalendarEvent(source="FED", title="PPI (May)", scheduled_time=_at_et(2026, 6, 11, 8, 30), importance="HIGH"),
    CalendarEvent(source="FED", title="Retail Sales (May)", scheduled_time=_at_et(2026, 6, 17, 8, 30), importance="HIGH"),
    CalendarEvent(source="FED", title="Industrial Production (May)", scheduled_time=_at_et(2026, 6, 17, 9, 15), importance="MED"),
    CalendarEvent(source="FED", title="Housing Starts (May)", scheduled_time=_at_et(2026, 6, 18, 8, 30), importance="MED"),
    CalendarEvent(source="FED", title="Existing Home Sales (May)", scheduled_time=_at_et(2026, 6, 22, 10, 0), importance="MED"),
    CalendarEvent(source="FED", title="GDP Q1 (3rd estimate)", scheduled_time=_at_et(2026, 6, 25, 8, 30), importance="HIGH"),
    CalendarEvent(source="FED", title="Personal Income & Outlays / PCE (May)", scheduled_time=_at_et(2026, 6, 25, 8, 30), importance="HIGH"),
    CalendarEvent(source="FED", title="CPI (Jun)", scheduled_time=_at_et(2026, 7, 14, 8, 30), importance="HIGH"),
    CalendarEvent(source="FED", title="PPI (Jun)", scheduled_time=_at_et(2026, 7, 15, 8, 30), importance="HIGH"),
    CalendarEvent(source="FED", title="Retail Sales (Jun)", scheduled_time=_at_et(2026, 7, 16, 8, 30), importance="HIGH"),
    CalendarEvent(source="FED", title="CPI (Jul)", scheduled_time=_at_et(2026, 8, 12, 8, 30), importance="HIGH"),
    CalendarEvent(source="FED", title="PPI (Jul)", scheduled_time=_at_et(2026, 8, 13, 8, 30), importance="HIGH"),
    CalendarEvent(source="FED", title="Retail Sales (Jul)", scheduled_time=_at_et(2026, 8, 14, 8, 30), importance="HIGH"),
    CalendarEvent(source="FED", title="CPI (Aug)", scheduled_time=_at_et(2026, 9, 10, 8, 30), importance="HIGH"),
    CalendarEvent(source="FED", title="PPI (Aug)", scheduled_time=_at_et(2026, 9, 11, 8, 30), importance="HIGH"),
    CalendarEvent(source="FED", title="Retail Sales (Aug)", scheduled_time=_at_et(2026, 9, 16, 8, 30), importance="HIGH"),
    CalendarEvent(source="FED", title="CPI (Sep)", scheduled_time=_at_et(2026, 10, 14, 8, 30), importance="HIGH"),
    CalendarEvent(source="FED", title="PPI (Sep)", scheduled_time=_at_et(2026, 10, 15, 8, 30), importance="HIGH"),
    CalendarEvent(source="FED", title="Retail Sales (Sep)", scheduled_time=_at_et(2026, 10, 16, 8, 30), importance="HIGH"),
    CalendarEvent(source="FED", title="CPI (Oct)", scheduled_time=_at_et(2026, 11, 12, 8, 30), importance="HIGH"),
    CalendarEvent(source="FED", title="PPI (Oct)", scheduled_time=_at_et(2026, 11, 13, 8, 30), importance="HIGH"),
    CalendarEvent(source="FED", title="Retail Sales (Oct)", scheduled_time=_at_et(2026, 11, 17, 8, 30), importance="HIGH"),
    CalendarEvent(source="FED", title="CPI (Nov)", scheduled_time=_at_et(2026, 12, 10, 8, 30), importance="HIGH"),
    CalendarEvent(source="FED", title="PPI (Nov)", scheduled_time=_at_et(2026, 12, 11, 8, 30), importance="HIGH"),
    CalendarEvent(source="FED", title="Retail Sales (Nov)", scheduled_time=_at_et(2026, 12, 16, 8, 30), importance="HIGH"),
)

ECB_2026: tuple[CalendarEvent, ...] = (
    CalendarEvent(source="ECB", title="ECB monetary policy decision", scheduled_time=_at_cet(2026, 1, 22, 14, 15), importance="HIGH"),
    CalendarEvent(source="ECB", title="ECB press conference (Lagarde)", scheduled_time=_at_cet(2026, 1, 22, 14, 45), importance="HIGH"),
    CalendarEvent(source="ECB", title="ECB monetary policy decision", scheduled_time=_at_cet(2026, 3, 5, 14, 15), importance="HIGH"),
    CalendarEvent(source="ECB", title="ECB press conference (Lagarde)", scheduled_time=_at_cet(2026, 3, 5, 14, 45), importance="HIGH"),
    CalendarEvent(source="ECB", title="ECB monetary policy decision", scheduled_time=_at_cet(2026, 4, 16, 14, 15), importance="HIGH"),
    CalendarEvent(source="ECB", title="ECB press conference (Lagarde)", scheduled_time=_at_cet(2026, 4, 16, 14, 45), importance="HIGH"),
    CalendarEvent(source="ECB", title="ECB monetary policy decision", scheduled_time=_at_cet(2026, 6, 11, 14, 15), importance="HIGH"),
    CalendarEvent(source="ECB", title="ECB press conference (Lagarde)", scheduled_time=_at_cet(2026, 6, 11, 14, 45), importance="HIGH"),
    CalendarEvent(source="ECB", title="ECB monetary policy decision", scheduled_time=_at_cet(2026, 7, 23, 14, 15), importance="HIGH"),
    CalendarEvent(source="ECB", title="ECB press conference (Lagarde)", scheduled_time=_at_cet(2026, 7, 23, 14, 45), importance="HIGH"),
    CalendarEvent(source="ECB", title="ECB monetary policy decision", scheduled_time=_at_cet(2026, 9, 10, 14, 15), importance="HIGH"),
    CalendarEvent(source="ECB", title="ECB press conference (Lagarde)", scheduled_time=_at_cet(2026, 9, 10, 14, 45), importance="HIGH"),
    CalendarEvent(source="ECB", title="ECB monetary policy decision", scheduled_time=_at_cet(2026, 10, 29, 14, 15), importance="HIGH"),
    CalendarEvent(source="ECB", title="ECB press conference (Lagarde)", scheduled_time=_at_cet(2026, 10, 29, 14, 45), importance="HIGH"),
    CalendarEvent(source="ECB", title="ECB monetary policy decision", scheduled_time=_at_cet(2026, 12, 17, 14, 15), importance="HIGH"),
    CalendarEvent(source="ECB", title="ECB press conference (Lagarde)", scheduled_time=_at_cet(2026, 12, 17, 14, 45), importance="HIGH"),
)

EU_RELEASES_2026: tuple[CalendarEvent, ...] = (
    CalendarEvent(source="ECB", title="Euro area HICP flash (May)", scheduled_time=_at_cet(2026, 6, 2, 11, 0), importance="HIGH"),
    CalendarEvent(source="ECB", title="Euro area unemployment (Apr)", scheduled_time=_at_cet(2026, 6, 3, 11, 0), importance="MED"),
    CalendarEvent(source="ECB", title="Euro area Retail Sales (Apr)", scheduled_time=_at_cet(2026, 6, 4, 11, 0), importance="MED"),
    CalendarEvent(source="ECB", title="Euro area GDP Q1 (3rd est.)", scheduled_time=_at_cet(2026, 6, 5, 11, 0), importance="MED"),
    CalendarEvent(source="ECB", title="Euro area HICP final (May)", scheduled_time=_at_cet(2026, 6, 17, 11, 0), importance="MED"),
    CalendarEvent(source="ECB", title="Euro area HICP flash (Jun)", scheduled_time=_at_cet(2026, 6, 30, 11, 0), importance="HIGH"),
    CalendarEvent(source="ECB", title="Euro area HICP flash (Jul)", scheduled_time=_at_cet(2026, 7, 31, 11, 0), importance="HIGH"),
    CalendarEvent(source="ECB", title="Euro area HICP flash (Aug)", scheduled_time=_at_cet(2026, 8, 31, 11, 0), importance="HIGH"),
    CalendarEvent(source="ECB", title="Euro area HICP flash (Sep)", scheduled_time=_at_cet(2026, 10, 1, 11, 0), importance="HIGH"),
    CalendarEvent(source="ECB", title="Euro area HICP flash (Oct)", scheduled_time=_at_cet(2026, 10, 30, 11, 0), importance="HIGH"),
    CalendarEvent(source="ECB", title="Euro area HICP flash (Nov)", scheduled_time=_at_cet(2026, 11, 30, 11, 0), importance="HIGH"),
)

RIKSBANK_2026: tuple[CalendarEvent, ...] = (
    CalendarEvent(source="RIKSBANK", title="Riksbank rate decision + MPR", scheduled_time=_at_cet(2026, 1, 28, 9, 30), importance="HIGH"),
    CalendarEvent(source="RIKSBANK", title="Riksbank press conference", scheduled_time=_at_cet(2026, 1, 28, 11, 0), importance="HIGH"),
    CalendarEvent(source="RIKSBANK", title="Riksbank rate decision + MPR", scheduled_time=_at_cet(2026, 3, 25, 9, 30), importance="HIGH"),
    CalendarEvent(source="RIKSBANK", title="Riksbank press conference", scheduled_time=_at_cet(2026, 3, 25, 11, 0), importance="HIGH"),
    CalendarEvent(source="RIKSBANK", title="Riksbank rate decision", scheduled_time=_at_cet(2026, 5, 6, 9, 30), importance="HIGH"),
    CalendarEvent(source="RIKSBANK", title="Riksbank rate decision + MPR", scheduled_time=_at_cet(2026, 6, 17, 9, 30), importance="HIGH"),
    CalendarEvent(source="RIKSBANK", title="Riksbank press conference", scheduled_time=_at_cet(2026, 6, 17, 11, 0), importance="HIGH"),
    CalendarEvent(source="RIKSBANK", title="Riksbank rate decision", scheduled_time=_at_cet(2026, 9, 23, 9, 30), importance="HIGH"),
    CalendarEvent(source="RIKSBANK", title="Riksbank rate decision + MPR", scheduled_time=_at_cet(2026, 11, 5, 9, 30), importance="HIGH"),
    CalendarEvent(source="RIKSBANK", title="Riksbank press conference", scheduled_time=_at_cet(2026, 11, 5, 11, 0), importance="HIGH"),
    CalendarEvent(source="RIKSBANK", title="Riksbank rate decision", scheduled_time=_at_cet(2026, 12, 17, 9, 30), importance="HIGH"),
)


_ALL_STATIC: tuple[CalendarEvent, ...] = (
    FOMC_2026 + US_RELEASES_2026 + ECB_2026 + EU_RELEASES_2026 + RIKSBANK_2026
)


def _generate_recurring(window_start: date, window_end: date) -> list[CalendarEvent]:
    events: list[CalendarEvent] = []
    d = window_start
    while d <= window_end:
        if d.weekday() == 3:
            events.append(
                CalendarEvent(
                    source="FED",
                    title="Initial Jobless Claims (weekly)",
                    scheduled_time=datetime.combine(d, time(8, 30), tzinfo=_ET),
                    importance="MED",
                )
            )
        if d.weekday() == 4 and d.day <= 7:
            events.append(
                CalendarEvent(
                    source="FED",
                    title="Employment Situation / NFP",
                    scheduled_time=datetime.combine(d, time(8, 30), tzinfo=_ET),
                    importance="HIGH",
                )
            )
        d += timedelta(days=1)
    return events


def load_static_events(window_start: date, window_end: date) -> list[CalendarEvent]:
    in_window = [
        e for e in _ALL_STATIC
        if window_start <= e.scheduled_time.astimezone(_CET).date() <= window_end
    ]
    recurring = _generate_recurring(window_start, window_end)
    dedupe: dict[tuple[str, datetime, str], CalendarEvent] = {}
    for e in in_window + recurring:
        key = (e.source, e.scheduled_time, e.title.casefold())
        dedupe.setdefault(key, e)
    return list(dedupe.values())


def window_around(today: date) -> tuple[date, date]:
    return today, today + timedelta(days=5)
