"""Insider watchlist + SEC contact come from config/env, not hardcoded source."""

from __future__ import annotations

import pytest

from goldsilver.data import insider_service as ins
from goldsilver.data.settings import AppSettings


def test_default_insider_tickers_parse_into_pairs() -> None:
    settings = AppSettings()

    assert settings.insider_ticker_pairs() == (("DJT", "0001849635"),)


def test_insider_tickers_cleaned_uppercased_and_deduped() -> None:
    settings = AppSettings(
        insider_tickers=["aapl:320193", "AAPL:320193", "DJT:0001849635"]
    )

    assert settings.insider_tickers == ["AAPL:320193", "DJT:0001849635"]
    assert settings.insider_ticker_pairs() == (
        ("AAPL", "320193"),
        ("DJT", "0001849635"),
    )


def test_malformed_insider_entries_are_dropped() -> None:
    settings = AppSettings(insider_tickers=["bad", "NO:cik", "OK:12345"])

    assert settings.insider_tickers == ["OK:12345"]


def test_empty_insider_list_opts_out_without_falling_back() -> None:
    settings = AppSettings(insider_tickers=[])

    assert settings.insider_tickers == []
    assert settings.insider_ticker_pairs() == ()


def test_corrupt_insider_value_resets_to_default() -> None:
    settings = AppSettings(insider_tickers="not-a-list")  # type: ignore[arg-type]

    assert settings.insider_tickers == ["DJT:0001849635"]


def test_sec_user_agent_is_generic_without_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(ins.SEC_CONTACT_ENV, raising=False)

    headers = ins._headers()

    assert headers["User-Agent"] == "gold-and-silver-tui"
    assert "@" not in headers["User-Agent"]


def test_sec_user_agent_appends_configured_contact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ins.SEC_CONTACT_ENV, "ops@example.com")

    headers = ins._headers()

    assert headers["User-Agent"] == "gold-and-silver-tui (ops@example.com)"
