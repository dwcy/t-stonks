"""Fetch released figures for a passed macro event via the Claude CLI and merge them in."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timedelta

from typing import cast

from pydantic import BaseModel, ValidationError

from goldsilver.data.calendar_actuals_store import event_key
from goldsilver.data.models_macro import (
    CalendarDay,
    CalendarEvent,
    CalendarSnapshot,
    EventAnalysis,
    ImpactDirection,
    SurpriseDirection,
)
from goldsilver.data.session import STOCKHOLM
from goldsilver.reports.claude_runner import ClaudeResult, run_claude
from goldsilver.reports.models import ReportStatus

ACTUALS_ALLOWED_TOOLS: list[str] = ["WebSearch", "WebFetch"]
FETCHABLE_IMPORTANCE: frozenset[str] = frozenset({"HIGH", "MED"})

_RELEASED_RE = re.compile(r"<!--\s*RELEASED:\s*(\{.*?\})\s*-->", re.DOTALL)


class ReleasedAnalysis(BaseModel):
    surprise: str | None = None
    gold: str | None = None
    silver: str | None = None
    usd: str | None = None
    rationale: str | None = None


class ReleasedFigures(BaseModel):
    found: bool = False
    actual: str | None = None
    forecast: str | None = None
    previous: str | None = None
    summary: str | None = None
    analysis: ReleasedAnalysis | None = None


_DIRECTIONS: frozenset[str] = frozenset({"bullish", "bearish", "neutral"})
_SURPRISES: frozenset[str] = frozenset({"above", "below", "inline", "na"})


def _direction(value: str | None) -> ImpactDirection:
    cleaned = (value or "").strip().lower()
    return cast(ImpactDirection, cleaned) if cleaned in _DIRECTIONS else "neutral"


def _surprise(value: str | None) -> SurpriseDirection:
    cleaned = (value or "").strip().lower()
    return cast(SurpriseDirection, cleaned) if cleaned in _SURPRISES else "na"


def _to_analysis(raw: ReleasedAnalysis | None) -> EventAnalysis | None:
    if raw is None:
        return None
    return EventAnalysis(
        surprise=_surprise(raw.surprise),
        gold=_direction(raw.gold),
        silver=_direction(raw.silver),
        usd=_direction(raw.usd),
        rationale=(raw.rationale or "").strip(),
    )


def build_actuals_prompt(
    event: CalendarEvent, same_day_events: tuple[str, ...] = ()
) -> str:
    local = event.scheduled_time.astimezone(STOCKHOLM)
    when = local.strftime("%Y-%m-%d %H:%M %Z")
    same_day_note = ""
    if same_day_events:
        listed = "; ".join(same_day_events)
        same_day_note = (
            "\n\nOther HIGH/MED-importance releases scheduled the same day: "
            f"{listed}. Check whether the actual market reaction was driven by one "
            "of these instead (e.g. a monthly payrolls/employment report outweighs "
            "a routine weekly claims print, or a bigger surprise elsewhere overrides "
            "a marginal beat/miss here). If so, your directional call must reflect "
            "the dominant, combined reaction rather than this print's mechanical "
            "read in isolation, and the rationale should name which release actually "
            "drove the move."
        )
    return (
        "You are a markets data assistant. Find the OFFICIAL released figures for this "
        "specific scheduled macro-economic release, using web search/fetch of primary "
        "sources (the issuing agency, central bank, or a reputable wire).\n\n"
        f"Source: {event.source}\n"
        f"Release: {event.title}\n"
        f"Scheduled (Europe/Stockholm): {when}\n\n"
        "Report the headline actual value, the market consensus/forecast, and the "
        "previous value. For a rate decision, the 'actual' is the new policy rate (or "
        "the decision, e.g. 'hold 4.25%'). Keep each value short (e.g. '3.2%', "
        "'+250k', '4.25%'). Write a one-sentence plain-language summary.\n\n"
        "Then assess the market impact, checking how gold, silver, and the dollar "
        "actually moved around this release rather than assuming the textbook "
        'mechanical read. Compare the actual to the consensus to set "surprise" to '
        "above, below, or inline. Give the likely directional impact on gold, "
        "silver, and the US dollar as bullish, bearish, or neutral (e.g. a "
        "hotter-than-expected CPI is usd bullish and gold bearish via "
        "higher-for-longer rate expectations; metals are non-yielding and move "
        "inversely to real yields and the dollar). A small beat or miss on a "
        "routine/secondary release is a weak signal on its own and can easily be "
        "overridden by other same-day data, wages, yields, or Fed-pricing — lean "
        "toward neutral rather than a strong call unless the surprise itself is "
        f"large.{same_day_note}\n\n"
        "Write a one- or two-sentence rationale naming the transmission to the "
        "dollar and to the metals, and note explicitly if the move was actually "
        "driven by a different same-day release rather than this one.\n\n"
        "If the release has not actually happened yet or you cannot confirm the figures "
        'from a primary source, set "found": false and leave the values null.\n\n'
        "Output ONLY a single HTML comment on its own line, nothing else, exactly in "
        "this form:\n"
        '<!-- RELEASED: {"found": true, "actual": "3.2%", "forecast": "3.1%", '
        '"previous": "3.0%", "summary": "Headline CPI rose 3.2% y/y, above the 3.1% '
        'consensus.", "analysis": {"surprise": "above", "gold": "bearish", '
        '"silver": "bearish", "usd": "bullish", "rationale": "A hotter CPI lifts '
        "rate-cut-delay odds, supporting the dollar and pressuring non-yielding gold "
        'and silver."}} -->'
    )


def same_day_titles(
    snapshot: CalendarSnapshot, event: CalendarEvent
) -> tuple[str, ...]:
    """Titles of other HIGH/MED events scheduled the same calendar day as ``event``."""
    target = _event_key(event)
    target_date = event.scheduled_time.astimezone(STOCKHOLM).date()
    titles: list[str] = []
    for day in snapshot.days:
        if day.date != target_date:
            continue
        for sibling in day.events:
            if _event_key(sibling) == target:
                continue
            if sibling.importance not in FETCHABLE_IMPORTANCE:
                continue
            titles.append(sibling.title)
    return tuple(titles)


def parse_released(text: str) -> ReleasedFigures | None:
    match = _RELEASED_RE.search(text)
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
        return ReleasedFigures.model_validate(data)
    except (json.JSONDecodeError, ValidationError, TypeError):
        return None


def _merge(event: CalendarEvent, figures: ReleasedFigures) -> CalendarEvent:
    return event.model_copy(
        update={
            "actual": figures.actual,
            "forecast": figures.forecast or event.forecast,
            "previous": figures.previous or event.previous,
            "actual_summary": figures.summary,
            "analysis": _to_analysis(figures.analysis),
            "status": "RELEASED",
        }
    )


class ActualsFetcher:
    """Fetches released figures once per event, capped by a concurrency semaphore."""

    def __init__(self, *, max_concurrency: int = 2, timeout_seconds: int = 180) -> None:
        self._sem = asyncio.Semaphore(max(1, max_concurrency))
        self._timeout_seconds = timeout_seconds
        self._dispatched: set[str] = set()

    def should_fetch(self, event: CalendarEvent) -> bool:
        return event_key(event) not in self._dispatched

    async def fetch(
        self, event: CalendarEvent, same_day_events: tuple[str, ...] = ()
    ) -> CalendarEvent | None:
        key = event_key(event)
        if key in self._dispatched:
            return None
        self._dispatched.add(key)
        async with self._sem:
            result: ClaudeResult = await run_claude(
                build_actuals_prompt(event, same_day_events),
                allowed_tools=ACTUALS_ALLOWED_TOOLS,
                timeout_seconds=self._timeout_seconds,
            )
        if result.status is not ReportStatus.SUCCESS or result.html is None:
            self._dispatched.discard(key)
            return None
        figures = parse_released(result.html)
        if figures is None or not figures.found or figures.actual is None:
            self._dispatched.discard(key)
            return None
        return _merge(event, figures)


def _event_key(event: CalendarEvent) -> tuple[str, datetime, str]:
    return (event.source, event.scheduled_time, event.title)


def due_events(
    snapshot: CalendarSnapshot,
    now_utc: datetime,
    grace_minutes: int,
) -> list[CalendarEvent]:
    """Today's HIGH/MED timed events whose scheduled time + grace has passed."""
    cutoff = now_utc - timedelta(minutes=grace_minutes)
    out: list[CalendarEvent] = []
    for day in snapshot.days:
        if day.bucket != "today":
            continue
        for event in day.events:
            if event.all_day or event.status == "RELEASED":
                continue
            if event.importance not in FETCHABLE_IMPORTANCE:
                continue
            if event.scheduled_time <= cutoff:
                out.append(event)
    return out


def merge_event(snapshot: CalendarSnapshot, updated: CalendarEvent) -> CalendarSnapshot:
    """Return a new snapshot with the event matching ``updated``'s key replaced."""
    target = _event_key(updated)
    days: list[CalendarDay] = []
    for day in snapshot.days:
        events = tuple(updated if _event_key(e) == target else e for e in day.events)
        days.append(day.model_copy(update={"events": events}))
    return snapshot.model_copy(update={"days": tuple(days)})
