"""Fetch the consensus forecast + anticipated metals/USD impact for an upcoming event."""

from __future__ import annotations

import json
import re

from pydantic import BaseModel, ValidationError

from goldsilver.data.calendar_actuals import ReleasedAnalysis, _to_analysis
from goldsilver.data.models_macro import CalendarEvent
from goldsilver.data.session import STOCKHOLM
from goldsilver.reports.claude_runner import ClaudeResult, run_claude
from goldsilver.reports.models import ReportStatus

EXPECTATIONS_ALLOWED_TOOLS: list[str] = ["WebSearch", "WebFetch"]

_EXPECTED_RE = re.compile(r"<!--\s*EXPECTED:\s*(\{.*?\})\s*-->", re.DOTALL)


class ExpectedFigures(BaseModel):
    found: bool = False
    forecast: str | None = None
    previous: str | None = None
    summary: str | None = None
    analysis: ReleasedAnalysis | None = None


def build_expectations_prompt(
    event: CalendarEvent, same_day_events: tuple[str, ...] = ()
) -> str:
    local = event.scheduled_time.astimezone(STOCKHOLM)
    when = local.strftime("%Y-%m-%d %H:%M %Z")
    same_day_note = ""
    if same_day_events:
        listed = "; ".join(same_day_events)
        same_day_note = (
            "\n\nOther HIGH/MED-importance releases scheduled the same day: "
            f"{listed}. If one of these dominates the session's metals/dollar reaction, "
            "say so in the rationale."
        )
    return (
        "You are a markets data assistant. This macro-economic release has NOT happened "
        "yet. Find the market CONSENSUS/FORECAST for it (and the PREVIOUS value for "
        "context) from primary or reputable sources via web search/fetch — do NOT invent "
        "or guess a released 'actual', because none exists yet.\n\n"
        f"Source: {event.source}\n"
        f"Release: {event.title}\n"
        f"Scheduled (Europe/Stockholm): {when}\n\n"
        "Report the consensus/forecast figure and the previous value, each short (e.g. "
        "'3.2%', '+250k', '4.25%'). Write a one-sentence plain-language summary of what "
        "is expected.\n\n"
        "Then assess the ANTICIPATED market impact ASSUMING the release lands ON "
        "consensus: give the likely directional impact on gold, silver, and the US dollar "
        "as bullish, bearish, or neutral (metals are non-yielding and move inversely to "
        "real yields and the dollar; e.g. an in-line hot CPI that confirms "
        "higher-for-longer is mildly usd bullish / gold bearish, but a fully-priced "
        "in-line print is often neutral). In the rationale, ALSO state the risk skew — "
        "which way a beat vs a miss would push gold/silver/the dollar — so the reader "
        f"knows the asymmetry around the forecast.{same_day_note}\n\n"
        'If you cannot find a credible consensus/forecast, set "found": false and leave '
        "the values null.\n\n"
        "Output ONLY a single HTML comment on its own line, nothing else, exactly in this "
        "form:\n"
        '<!-- EXPECTED: {"found": true, "forecast": "3.1%", "previous": "3.0%", '
        '"summary": "Consensus sees headline CPI at 3.1% y/y, up from 3.0%.", '
        '"analysis": {"gold": "neutral", "silver": "neutral", "usd": "neutral", '
        '"rationale": "An in-line print is largely priced; a hotter beat would lift the '
        'dollar and pressure gold/silver, while a miss would do the reverse."}} -->'
    )


def parse_expected(text: str) -> ExpectedFigures | None:
    match = _EXPECTED_RE.search(text)
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
        return ExpectedFigures.model_validate(data)
    except (json.JSONDecodeError, ValidationError, TypeError):
        return None


def merge_expected(event: CalendarEvent, figures: ExpectedFigures) -> CalendarEvent:
    """Populate forecast/previous/expected_summary + anticipated analysis, leaving
    `actual` and `status` untouched — this is a preview, not a release."""
    return event.model_copy(
        update={
            "forecast": figures.forecast or event.forecast,
            "previous": figures.previous or event.previous,
            "expected_summary": figures.summary,
            "analysis": _to_analysis(figures.analysis),
        }
    )


async def fetch_expected(
    event: CalendarEvent,
    same_day_events: tuple[str, ...] = (),
    *,
    timeout_seconds: int = 180,
) -> CalendarEvent | None:
    result: ClaudeResult = await run_claude(
        build_expectations_prompt(event, same_day_events),
        allowed_tools=EXPECTATIONS_ALLOWED_TOOLS,
        timeout_seconds=timeout_seconds,
    )
    if result.status is not ReportStatus.SUCCESS or result.html is None:
        return None
    figures = parse_expected(result.html)
    if figures is None or not figures.found:
        return None
    return merge_expected(event, figures)
