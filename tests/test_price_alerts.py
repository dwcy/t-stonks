"""Tests for the price-alert engine, input parsing, and the alerts modal."""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Label

from goldsilver.data.alerts import PriceAlertEngine
from goldsilver.data.settings import AppSettings
from goldsilver.widgets.alerts_screen import AlertsScreen, parse_alert_input

_CSS = (
    Path(__file__).resolve().parents[1] / "src" / "goldsilver" / "styles" / "app.tcss"
)


def test_engine_arms_then_fires_on_cross() -> None:
    engine = PriceAlertEngine()

    assert engine.check("XAU", 2690.0, [2700.0]) == []  # arming, no alert
    assert engine.check("XAU", 2695.0, [2700.0]) == []
    assert engine.check("XAU", 2701.0, [2700.0]) == [(2700.0, True)]
    assert engine.check("XAU", 2705.0, [2700.0]) == []  # stays above, no repeat
    assert engine.check("XAU", 2698.0, [2700.0]) == [(2700.0, False)]


def test_engine_tracks_levels_independently() -> None:
    engine = PriceAlertEngine()
    engine.check("XAU", 2650.0, [2600.0, 2700.0])

    fired = engine.check("XAU", 2710.0, [2600.0, 2700.0])

    assert fired == [(2700.0, True)]


def test_parse_alert_input_aliases_and_garbage() -> None:
    assert parse_alert_input("gold 2700") == ("XAU", 2700.0)
    assert parse_alert_input("XAG 36,5") == ("XAG", 36.5)
    assert parse_alert_input("NVDA 100") is None
    assert parse_alert_input("XAU") is None
    assert parse_alert_input("XAU -5") is None


class _Host(App[None]):
    CSS_PATH = str(_CSS)

    def compose(self) -> ComposeResult:
        yield Label("host")


async def test_alerts_screen_add_and_remove() -> None:
    settings = AppSettings()
    changes = {"n": 0}
    app = _Host()
    async with app.run_test(size=(100, 40)) as pilot:
        screen = AlertsScreen(
            settings, on_change=lambda: changes.__setitem__("n", changes["n"] + 1)
        )
        await app.push_screen(screen)
        await pilot.pause()

        screen._add_alert("xau 2700")
        assert settings.price_alerts == {"XAU": [2700.0]}
        screen._add_alert("silver 36.5")
        assert settings.price_alerts == {"XAU": [2700.0], "XAG": [36.5]}

        screen._remove_alert(0)
        assert settings.price_alerts == {"XAG": [36.5]}
        assert changes["n"] == 3
