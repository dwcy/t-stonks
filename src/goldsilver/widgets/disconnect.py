from __future__ import annotations

from typing import Callable

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Label


class DisconnectScreen(ModalScreen[None]):
    BINDINGS = [("escape", "dismiss", "Dismiss")]

    def __init__(
        self, *, on_user_dismiss: Callable[[], None] | None = None
    ) -> None:
        super().__init__()
        self._on_user_dismiss = on_user_dismiss
        self._programmatic = False

    def compose(self) -> ComposeResult:
        with Container(id="disconnect-dialog"):
            yield Label("● LIVE FEED DISCONNECTED", id="disconnect-title")
            yield Label(
                "Lost connection to goldprice.org.", id="disconnect-body"
            )
            yield Label(
                "Auto-retrying every 5s…", id="disconnect-retry"
            )
            yield Label("Press Esc to dismiss.", id="disconnect-hint")

    def dismiss_programmatically(self) -> None:
        self._programmatic = True
        self.dismiss()

    async def action_dismiss(self, result: None = None) -> None:
        if not self._programmatic and self._on_user_dismiss is not None:
            self._on_user_dismiss()
        await super().action_dismiss(result)
