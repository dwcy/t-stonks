"""Modal screen to manage the report watchlist, toggle automation, and open reports."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Switch

from goldsilver.data.settings import ReportSettings
from goldsilver.reports.constants import METAL_LABELS, PINNED_METALS, safe_name
from goldsilver.reports.models import ReportRun, ReportStatus


class ReportWatchlistScreen(ModalScreen[None]):
    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(
        self,
        settings: ReportSettings,
        *,
        on_change: Callable[[], None],
        on_generate: Callable[[], None],
        on_open: Callable[[ReportRun], None],
        recent: Sequence[ReportRun] = (),
    ) -> None:
        super().__init__()
        self._settings = settings
        self._on_change = on_change
        self._on_generate = on_generate
        self._on_open = on_open
        self._recent = list(recent)

    def compose(self) -> ComposeResult:
        with Container(id="report-dialog"):
            yield Label("Reports", id="report-title")
            with VerticalScroll(id="report-body"):
                with Horizontal(classes="report-switch-row"):
                    yield Switch(value=self._settings.enabled, id="report-enabled")
                    yield Label("Hourly automation", classes="report-switch-label")
                with Horizontal(classes="report-switch-row"):
                    yield Label("Interval (min)", classes="report-sub-label")
                    yield Input(
                        value=str(self._settings.interval_minutes),
                        id="report-interval",
                        classes="report-interval",
                    )
                yield Label("Always analyzed", classes="report-section-label")
                for sym in PINNED_METALS:
                    yield Label(
                        f"  • {METAL_LABELS.get(sym, sym)} ({sym}) — pinned",
                        classes="report-pinned",
                    )
                yield Label("Watchlist", classes="report-section-label")
                with Vertical(id="report-ticker-list"):
                    for row in self._build_ticker_rows():
                        yield row
                with Horizontal(classes="report-add-row"):
                    yield Input(
                        placeholder="add ticker e.g. NVDA, VOLV-B.ST",
                        id="report-add-input",
                    )
                    yield Button("Add", variant="default", id="report-add")
                yield Label("Recent reports", classes="report-section-label")
                with Vertical(id="report-recent-list"):
                    for row in self._build_recent_rows():
                        yield row
            with Horizontal(id="report-actions"):
                yield Button("Generate now", variant="primary", id="report-generate")
                yield Button("Close", id="report-close")

    def _build_ticker_rows(self) -> list[Horizontal]:
        rows: list[Horizontal] = []
        if not self._settings.report_tickers:
            rows.append(Horizontal(Label("(no stocks added)", classes="report-empty")))
            return rows
        for sym in self._settings.report_tickers:
            rows.append(
                Horizontal(
                    Label(sym, classes="report-ticker-label"),
                    Button("✕", id=f"rm-{safe_name(sym)}", classes="report-remove"),
                    classes="report-ticker-row",
                )
            )
        return rows

    def _build_recent_rows(self) -> list[Horizontal]:
        rows: list[Horizontal] = []
        if not self._recent:
            rows.append(Horizontal(Label("(none yet)", classes="report-empty")))
            return rows
        for i, run in enumerate(self._recent):
            rows.append(
                Horizontal(
                    Label(self._recent_label(run), classes="report-recent-label"),
                    Button("open", id=f"open-{i}", classes="report-open"),
                    classes="report-recent-row",
                )
            )
        return rows

    @staticmethod
    def _recent_label(run: ReportRun) -> str:
        when = run.started_at.strftime("%H:%M")
        if run.verdict is not None:
            tag = f"{run.verdict.intraday} {run.verdict.confidence}%"
        elif run.status in (ReportStatus.SUCCESS, ReportStatus.MALFORMED):
            tag = "—"
        else:
            tag = run.status.value
        return f"{when}  {run.ticker:<8}  {tag}"

    def _refresh_tickers(self) -> None:
        container = self.query_one("#report-ticker-list", Vertical)
        container.remove_children()
        container.mount(*self._build_ticker_rows())

    def _add_ticker(self, raw: str) -> None:
        sym = raw.strip().upper()
        if not sym or sym in self._settings.report_tickers or sym in PINNED_METALS:
            return
        self._settings.report_tickers.append(sym)
        self._refresh_tickers()
        self._on_change()

    def _remove_ticker(self, sym: str) -> None:
        if sym in self._settings.report_tickers:
            self._settings.report_tickers.remove(sym)
            self._refresh_tickers()
            self._on_change()

    def on_switch_changed(self, event: Switch.Changed) -> None:
        if event.switch.id == "report-enabled":
            self._settings.enabled = event.value
            self._on_change()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "report-add-input":
            self._add_ticker(event.value)
            event.input.value = ""

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "report-interval":
            return
        try:
            minutes = int(event.value)
        except ValueError:
            return
        self._settings.interval_minutes = minutes
        self._settings.__post_init__()
        self._on_change()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "report-close":
            self.dismiss()
        elif bid == "report-generate":
            self._on_generate()
        elif bid == "report-add":
            field = self.query_one("#report-add-input", Input)
            self._add_ticker(field.value)
            field.value = ""
        elif bid.startswith("rm-"):
            target = bid[len("rm-") :]
            for sym in list(self._settings.report_tickers):
                if safe_name(sym) == target:
                    self._remove_ticker(sym)
                    break
        elif bid.startswith("open-"):
            try:
                idx = int(bid[len("open-") :])
            except ValueError:
                return
            if 0 <= idx < len(self._recent):
                self._on_open(self._recent[idx])
