"""Tests for FRED DFII10 observation parsing."""

from __future__ import annotations

from datetime import date

from goldsilver.data.yields_service import parse_observations


def test_parses_latest_two_valid_observations() -> None:
    payload = {
        "observations": [
            {"date": "2026-06-10", "value": "."},
            {"date": "2026-06-09", "value": "2.11"},
            {"date": "2026-06-08", "value": "2.08"},
            {"date": "2026-06-05", "value": "2.01"},
        ]
    }

    point = parse_observations(payload)

    assert point is not None
    assert point.value == 2.11
    assert point.previous == 2.08
    assert point.asof == date(2026, 6, 9)


def test_single_valid_observation_has_no_previous() -> None:
    payload = {"observations": [{"date": "2026-06-09", "value": "2.11"}]}

    point = parse_observations(payload)

    assert point is not None
    assert point.previous is None


def test_garbage_payload_returns_none() -> None:
    assert parse_observations({}) is None
    assert parse_observations({"observations": [{"date": "x", "value": "."}]}) is None
