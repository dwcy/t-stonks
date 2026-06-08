"""Mount-and-render smoke tests for the report watchlist modal."""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Label

from goldsilver.data.settings import ReportSettings
from goldsilver.widgets.report_watchlist import ReportWatchlistScreen

_CSS = (
    Path(__file__).resolve().parents[1] / "src" / "goldsilver" / "styles" / "app.tcss"
)
_SIZE = (120, 50)


class _Host(App[None]):
    CSS_PATH = str(_CSS)

    def compose(self) -> ComposeResult:
        yield Label("host")


def _make_screen(settings: ReportSettings, sink: dict):
    return ReportWatchlistScreen(
        settings,
        on_change=lambda: sink.__setitem__("changes", sink.get("changes", 0) + 1),
        on_generate=lambda: sink.__setitem__("gen", sink.get("gen", 0) + 1),
        on_open=lambda run: sink.setdefault("opened", []).append(run),
    )


async def _click(pilot, selector: str) -> None:
    pilot.app.screen.query_one(selector).scroll_visible(animate=False)
    await pilot.pause()
    await pilot.click(selector)
    await pilot.pause()


async def test_mounts_with_pinned_metals() -> None:
    settings = ReportSettings(report_tickers=["NVDA"])
    sink: dict = {}
    app = _Host()
    async with app.run_test(size=_SIZE) as pilot:
        await app.push_screen(_make_screen(settings, sink))
        await pilot.pause()
        pinned = app.screen.query(".report-pinned")
        assert len(pinned) == 2  # Gold + Silver, always present
        # No remove control exists for pinned metals.
        assert len(app.screen.query("#rm-XAU")) == 0
        assert len(app.screen.query("#rm-XAG")) == 0


async def test_add_ticker_persists() -> None:
    settings = ReportSettings(report_tickers=[])
    sink: dict = {}
    app = _Host()
    async with app.run_test(size=_SIZE) as pilot:
        await app.push_screen(_make_screen(settings, sink))
        await pilot.pause()
        app.screen.query_one("#report-add-input").value = "volv-b.st"
        await _click(pilot, "#report-add")
        assert settings.report_tickers == ["VOLV-B.ST"]
        assert sink.get("changes", 0) >= 1


async def test_blank_and_duplicate_dropped() -> None:
    settings = ReportSettings(report_tickers=["NVDA"])
    sink: dict = {}
    app = _Host()
    async with app.run_test(size=_SIZE) as pilot:
        screen = _make_screen(settings, sink)
        await app.push_screen(screen)
        await pilot.pause()
        screen._add_ticker("   ")
        screen._add_ticker("NVDA")
        assert settings.report_tickers == ["NVDA"]


async def test_remove_stock() -> None:
    settings = ReportSettings(report_tickers=["NVDA"])
    sink: dict = {}
    app = _Host()
    async with app.run_test(size=_SIZE) as pilot:
        await app.push_screen(_make_screen(settings, sink))
        await pilot.pause()
        await _click(pilot, "#rm-NVDA")
        assert settings.report_tickers == []


async def test_generate_button_fires_callback() -> None:
    settings = ReportSettings(report_tickers=["NVDA"])
    sink: dict = {}
    app = _Host()
    async with app.run_test(size=_SIZE) as pilot:
        await app.push_screen(_make_screen(settings, sink))
        await pilot.pause()
        await _click(pilot, "#report-generate")
        assert sink.get("gen", 0) == 1
