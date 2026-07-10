"""Tests for the Riksbank policy-rate observation parser."""

from __future__ import annotations

from datetime import date

from goldsilver.data.riksbank_client import parse_observations


def test_takes_latest_and_last_distinct_prior_value() -> None:
    rows = [
        {"date": "2026-05-01", "value": 2.0},
        {"date": "2026-06-01", "value": 2.0},
        {"date": "2026-07-01", "value": 1.75},
        {"date": "2026-07-10", "value": 1.75},
    ]

    obs = parse_observations(rows)

    assert obs is not None
    assert obs.value == 1.75
    assert obs.previous == 2.0
    assert obs.asof == date(2026, 7, 10)


def test_unsorted_rows_are_handled() -> None:
    rows = [
        {"date": "2026-07-10", "value": 1.75},
        {"date": "2026-01-01", "value": 2.0},
    ]

    obs = parse_observations(rows)

    assert obs is not None
    assert obs.value == 1.75
    assert obs.asof == date(2026, 7, 10)


def test_all_flat_values_has_no_previous() -> None:
    rows = [
        {"date": "2026-07-01", "value": 1.75},
        {"date": "2026-07-10", "value": 1.75},
    ]

    obs = parse_observations(rows)

    assert obs is not None
    assert obs.previous is None


def test_garbage_payload_returns_none() -> None:
    assert parse_observations(None) is None
    assert parse_observations([]) is None
    assert parse_observations([{"date": "not-a-date", "value": "x"}]) is None
