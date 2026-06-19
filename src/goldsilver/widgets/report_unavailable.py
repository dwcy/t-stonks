"""Modal shown when the `claude` CLI is missing, so AI reports cannot run."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class ReportUnavailableScreen(ModalScreen[None]):
    BINDINGS = [("escape", "dismiss", "Close")]

    _LINES = (
        "AI-generated reports need the integrated Claude CLI, but it was not "
        "found on your PATH.",
        "",
        "Install it and sign in with your existing subscription:",
        "  • npm install -g @anthropic-ai/claude-code",
        "  • run `claude` once to log in",
        "",
        "Reports reuse that CLI login — no API key is required. Reopen this "
        "screen once `claude` is on your PATH.",
    )

    def compose(self) -> ComposeResult:
        with Container(id="report-dialog"):
            yield Label("Reports unavailable", id="report-title")
            with VerticalScroll(id="report-body"):
                for line in self._LINES:
                    yield Label(line, classes="report-unavailable-line")
            with Horizontal(id="report-actions"):
                yield Button("Close", variant="primary", id="report-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "report-close":
            self.dismiss()
