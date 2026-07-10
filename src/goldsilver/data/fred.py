"""Shared FRED (St. Louis Fed) fetch/parse, reused by yields, rates, and calendar services."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from typing import Any

from goldsilver.data.http import make_client

FRED_OBS_URL = "https://api.stlouisfed.org/fred/series/observations"
FRED_KEY_ENV = "GOLDSILVER_FRED_KEY"


def fred_api_key() -> str:
    return os.environ.get(FRED_KEY_ENV, "").strip()


@dataclass(slots=True)
class FredObservation:
    value: float
    previous: float | None
    asof: date


def parse_fred_pair(payload: dict[str, Any]) -> FredObservation | None:
    """Newest-first FRED observations -> latest + previous valid values."""
    observations = payload.get("observations")
    if not isinstance(observations, list):
        return None
    valid: list[tuple[date, float]] = []
    for obs in observations:
        if not isinstance(obs, dict):
            continue
        raw = str(obs.get("value", ".")).strip()
        if raw in (".", ""):
            continue
        try:
            valid.append((date.fromisoformat(str(obs.get("date"))), float(raw)))
        except ValueError:
            continue
        if len(valid) == 2:
            break
    if not valid:
        return None
    return FredObservation(
        value=valid[0][1],
        previous=valid[1][1] if len(valid) > 1 else None,
        asof=valid[0][0],
    )


async def fetch_fred_pair(
    series_id: str, *, api_key: str, timeout: float = 20.0
) -> FredObservation | None:
    async with make_client(timeout=timeout) as client:
        response = await client.get(
            FRED_OBS_URL,
            params={
                "series_id": series_id,
                "api_key": api_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": 10,
            },
        )
        response.raise_for_status()
        payload = response.json()
    return parse_fred_pair(payload)
