"""Tests for the shared FRED observation parser (reused by yields/rates/calendar)."""

from __future__ import annotations

from datetime import date

from goldsilver.data.fred import parse_fred_pair


def test_parses_latest_two_valid_observations() -> None:
    payload = {
        "observations": [
            {"date": "2026-06-10", "value": "."},
            {"date": "2026-06-09", "value": "5.33"},
            {"date": "2026-06-08", "value": "5.33"},
            {"date": "2026-06-05", "value": "5.08"},
        ]
    }

    obs = parse_fred_pair(payload)

    assert obs is not None
    assert obs.value == 5.33
    assert obs.previous == 5.33
    assert obs.asof == date(2026, 6, 9)


def test_single_valid_observation_has_no_previous() -> None:
    payload = {"observations": [{"date": "2026-06-09", "value": "5.33"}]}

    obs = parse_fred_pair(payload)

    assert obs is not None
    assert obs.previous is None


def test_garbage_payload_returns_none() -> None:
    assert parse_fred_pair({}) is None
    assert parse_fred_pair({"observations": [{"date": "x", "value": "."}]}) is None
