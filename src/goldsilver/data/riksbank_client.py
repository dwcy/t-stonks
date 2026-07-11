"""Fetch Sweden's Riksbank policy rate via their public REST API (no key required)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import httpx

from goldsilver.data.http import make_client

RIKSBANK_OBS_URL = (
    "https://api.riksbank.se/swea/v1/Observations/{series_id}/{start}/{end}"
)
POLICY_RATE_SERIES = "SECBREPOEFF"
# Comfortably spans the gap between rate-decision meetings, so "previous" reflects
# the last genuine change rather than yesterday's repeated flat value.
_LOOKBACK_DAYS = 400


@dataclass(slots=True)
class RiksbankObservation:
    value: float
    previous: float | None
    asof: date


def parse_observations(rows: object) -> RiksbankObservation | None:
    """Ascending-date {date, value} rows -> latest value + last distinct prior value."""
    if not isinstance(rows, list):
        return None
    valid: list[tuple[date, float]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            valid.append((date.fromisoformat(str(row["date"])), float(row["value"])))
        except (KeyError, ValueError, TypeError):
            continue
    if not valid:
        return None
    valid.sort(key=lambda pair: pair[0])
    latest_date, latest_value = valid[-1]
    previous_value: float | None = None
    for _, value in reversed(valid[:-1]):
        if value != latest_value:
            previous_value = value
            break
    return RiksbankObservation(
        value=latest_value, previous=previous_value, asof=latest_date
    )


async def fetch_policy_rate(*, timeout: float = 20.0) -> RiksbankObservation | None:
    end = date.today()
    start = end - timedelta(days=_LOOKBACK_DAYS)
    url = RIKSBANK_OBS_URL.format(
        series_id=POLICY_RATE_SERIES, start=start.isoformat(), end=end.isoformat()
    )
    try:
        async with make_client(timeout=timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    return parse_observations(payload)
