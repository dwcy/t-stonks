"""Mount-and-render smoke tests for the reports-unavailable modal."""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Label

from goldsilver.widgets.report_unavailable import ReportUnavailableScreen

_CSS = (
    Path(__file__).resolve().parents[1] / "src" / "goldsilver" / "styles" / "app.tcss"
)
_SIZE = (120, 50)


class _Host(App[None]):
    CSS_PATH = str(_CSS)

    def compose(self) -> ComposeResult:
        yield Label("host")


async def test_mounts_and_shows_cli_message() -> None:
    app = _Host()
    async with app.run_test(size=_SIZE) as pilot:
        await app.push_screen(ReportUnavailableScreen())
        await pilot.pause()
        assert len(app.screen.query("#report-close")) == 1
        text = " ".join(
            str(label.render())
            for label in app.screen.query(".report-unavailable-line")
        )
        assert "Claude CLI" in text


async def test_close_button_dismisses() -> None:
    app = _Host()
    async with app.run_test(size=_SIZE) as pilot:
        await app.push_screen(ReportUnavailableScreen())
        await pilot.pause()
        assert app.screen.query_one("#report-close") is not None
        await pilot.click("#report-close")
        await pilot.pause()
        assert not isinstance(app.screen, ReportUnavailableScreen)
