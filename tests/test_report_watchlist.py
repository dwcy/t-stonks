"""Mount-and-render smoke tests for the report watchlist modal."""

from __future__ import annotations

from datetime import datetime
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
        on_retry=lambda sym: sink.setdefault("retried", []).append(sym),
        on_delete=lambda run: sink.setdefault("deleted", []).append(run),
    )


async def _click(pilot, selector: str) -> None:
    pilot.app.screen.query_one(selector).scroll_visible(animate=False)
    await pilot.pause()
    await pilot.click(selector)
    await pilot.pause()


async def test_mounts_with_unified_watchlist() -> None:
    settings = ReportSettings(report_tickers=["NVDA"])
    sink: dict = {}
    app = _Host()
    async with app.run_test(size=_SIZE) as pilot:
        await app.push_screen(_make_screen(settings, sink))
        await pilot.pause()
        # Metals are regular rows with include toggles and generate buttons,
        # but no remove control.
        assert len(app.screen.query("#inc-XAU")) == 1
        assert len(app.screen.query("#inc-XAG")) == 1
        assert len(app.screen.query("#gen-XAU")) == 1
        assert len(app.screen.query("#rm-XAU")) == 0
        assert len(app.screen.query("#rm-XAG")) == 0
        # Stocks get toggle, generate, and remove.
        assert len(app.screen.query("#inc-NVDA")) == 1
        assert len(app.screen.query("#gen-NVDA")) == 1
        assert len(app.screen.query("#rm-NVDA")) == 1


async def test_include_toggle_updates_excluded() -> None:
    settings = ReportSettings(report_tickers=["NVDA"])
    sink: dict = {}
    app = _Host()
    async with app.run_test(size=_SIZE) as pilot:
        await app.push_screen(_make_screen(settings, sink))
        await pilot.pause()
        await _click(pilot, "#inc-XAG")
        assert settings.report_excluded == ["XAG"]
        await _click(pilot, "#inc-XAG")
        assert settings.report_excluded == []
        assert sink.get("changes", 0) >= 2


async def test_row_generate_button_fires_single_symbol() -> None:
    settings = ReportSettings(report_tickers=["NVDA"])
    sink: dict = {}
    app = _Host()
    async with app.run_test(size=_SIZE) as pilot:
        await app.push_screen(_make_screen(settings, sink))
        await pilot.pause()
        await _click(pilot, "#gen-NVDA")
        assert sink.get("retried") == ["NVDA"]


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


async def test_generating_spinner_rows_then_cleared() -> None:
    from goldsilver.data.session import STOCKHOLM
    from goldsilver.reports.models import ReportRun, ReportStatus

    settings = ReportSettings(report_tickers=["NVDA"])
    sink: dict = {}
    app = _Host()
    async with app.run_test(size=_SIZE) as pilot:
        screen = _make_screen(settings, sink)
        await app.push_screen(screen)
        await pilot.pause()
        screen.mark_generating(["XAU", "XAG"])
        await pilot.pause()
        assert len(app.screen.query("#spin-XAU")) == 1
        assert len(app.screen.query("#spin-XAG")) == 1

        run = ReportRun(
            ticker="XAU",
            label="Gold",
            kind="metal",
            started_at=datetime(2026, 6, 8, 14, 0, tzinfo=STOCKHOLM),
            status=ReportStatus.SUCCESS,
        )
        screen.mark_done(run)
        await pilot.pause()
        assert len(app.screen.query("#spin-XAU")) == 0  # swapped to result
        assert len(app.screen.query("#spin-XAG")) == 1  # still generating
        labels = [
            str(label.render()) for label in app.screen.query(".report-recent-label")
        ]
        assert any("Gold" in text for text in labels)
        assert not any("XAU" in text for text in labels)


async def test_failed_run_shows_retry_and_fires_callback() -> None:
    from goldsilver.data.session import STOCKHOLM
    from goldsilver.reports.models import ReportRun, ReportStatus

    failed = ReportRun(
        ticker="XAG",
        label="Silver",
        kind="metal",
        started_at=datetime(2026, 6, 8, 14, 0, tzinfo=STOCKHOLM),
        status=ReportStatus.TIMEOUT,
    )
    success = ReportRun(
        ticker="XAU",
        label="Gold",
        kind="metal",
        started_at=datetime(2026, 6, 8, 14, 0, tzinfo=STOCKHOLM),
        status=ReportStatus.SUCCESS,
    )
    settings = ReportSettings(report_tickers=[])
    sink: dict = {}
    app = _Host()
    async with app.run_test(size=_SIZE) as pilot:
        screen = _make_screen(settings, sink)
        screen._recent = [failed, success]
        await app.push_screen(screen)
        await pilot.pause()
        # Failed run (index 0) has a retry button; the success run (index 1) does not.
        assert len(app.screen.query("#retry-0")) == 1
        assert len(app.screen.query("#retry-1")) == 0
        await _click(pilot, "#retry-0")
        assert sink.get("retried") == ["XAG"]


async def test_delete_button_fires_callback_and_removes_row() -> None:
    from goldsilver.data.session import STOCKHOLM
    from goldsilver.reports.models import ReportRun, ReportStatus

    run = ReportRun(
        ticker="NVDA",
        label="NVDA",
        kind="stock",
        started_at=datetime(2026, 6, 9, 14, 0, tzinfo=STOCKHOLM),
        status=ReportStatus.SUCCESS,
    )
    settings = ReportSettings(report_tickers=[])
    sink: dict = {}
    app = _Host()
    async with app.run_test(size=_SIZE) as pilot:
        screen = _make_screen(settings, sink)
        screen._recent = [run]
        await app.push_screen(screen)
        await pilot.pause()
        await _click(pilot, "#del-0")
        assert sink.get("deleted") == [run]
        assert len(app.screen.query("#del-0")) == 0  # row gone


async def test_timeout_input_updates_settings() -> None:
    settings = ReportSettings(report_tickers=[])
    sink: dict = {}
    app = _Host()
    async with app.run_test(size=_SIZE) as pilot:
        screen = _make_screen(settings, sink)
        await app.push_screen(screen)
        await pilot.pause()
        app.screen.query_one("#report-timeout").value = "540"
        await pilot.pause()
        assert settings.timeout_seconds == 540
