"""Modal screen to manage the report watchlist, toggle automation, and open reports."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Switch

from goldsilver.data.settings import ReportSettings
from goldsilver.reports.constants import METAL_LABELS, PINNED_METALS, safe_name
from goldsilver.reports.models import ReportRun, ReportStatus

_SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


class ReportWatchlistScreen(ModalScreen[None]):
    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(
        self,
        settings: ReportSettings,
        *,
        on_change: Callable[[], None],
        on_generate: Callable[[], None],
        on_open: Callable[[ReportRun], None],
        on_retry: Callable[[str], None],
        on_delete: Callable[[ReportRun], None],
        recent: Sequence[ReportRun] = (),
        generating: Sequence[str] = (),
    ) -> None:
        super().__init__()
        self._settings = settings
        self._on_change = on_change
        self._on_generate = on_generate
        self._on_open = on_open
        self._on_retry = on_retry
        self._on_delete = on_delete
        self._recent = list(recent)
        self._generating: list[str] = list(generating)
        self._spinner_frame = 0
        self._spinner_timer = None

    def compose(self) -> ComposeResult:
        with Container(id="report-dialog"):
            yield Label("Reports", id="report-title")
            with VerticalScroll(id="report-body"):
                with Horizontal(classes="report-switch-row"):
                    yield Switch(value=self._settings.enabled, id="report-enabled")
                    yield Label("Hourly automation", classes="report-switch-label")
                with Horizontal(classes="report-config-row"):
                    yield Label("Interval m", classes="report-cfg-label")
                    yield Input(
                        value=str(self._settings.interval_minutes),
                        id="report-interval",
                        classes="report-cfg-input",
                    )
                    yield Label("Timeout s", classes="report-cfg-label")
                    yield Input(
                        value=str(self._settings.timeout_seconds),
                        id="report-timeout",
                        classes="report-cfg-input",
                    )
                    yield Label("Parallel", classes="report-cfg-label")
                    yield Input(
                        value=str(self._settings.max_concurrency),
                        id="report-concurrency",
                        classes="report-cfg-input",
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
        frame = _SPINNER_FRAMES[self._spinner_frame]
        for sym in self._generating:
            rows.append(
                Horizontal(
                    Label(frame, id=f"spin-{safe_name(sym)}", classes="report-spinner"),
                    Label(f"{sym:<8}  generating…", classes="report-recent-label"),
                    classes="report-recent-row",
                )
            )
        if not self._generating and not self._recent:
            rows.append(Horizontal(Label("(none yet)", classes="report-empty")))
            return rows
        for i, run in enumerate(self._recent):
            children: list = [
                Label(self._recent_label(run), classes="report-recent-label")
            ]
            if run.status is not ReportStatus.SUCCESS:
                children.append(
                    Button("retry", id=f"retry-{i}", classes="report-retry")
                )
            children.append(Button("open", id=f"open-{i}", classes="report-open"))
            children.append(Button("✕", id=f"del-{i}", classes="report-remove"))
            rows.append(Horizontal(*children, classes="report-recent-row"))
        return rows

    def on_mount(self) -> None:
        if self._generating:
            self._start_spinner()

    def on_unmount(self) -> None:
        self._stop_spinner()

    def _start_spinner(self) -> None:
        if self._spinner_timer is None:
            self._spinner_timer = self.set_interval(0.12, self._tick_spinner)

    def _stop_spinner(self) -> None:
        if self._spinner_timer is not None:
            self._spinner_timer.stop()
            self._spinner_timer = None

    def _tick_spinner(self) -> None:
        self._spinner_frame = (self._spinner_frame + 1) % len(_SPINNER_FRAMES)
        frame = _SPINNER_FRAMES[self._spinner_frame]
        for sym in self._generating:
            try:
                self.query_one(f"#spin-{safe_name(sym)}", Label).update(frame)
            except NoMatches:
                pass

    def _refresh_recent(self) -> None:
        try:
            container = self.query_one("#report-recent-list", Vertical)
        except NoMatches:
            return
        container.remove_children()
        container.mount(*self._build_recent_rows())

    def mark_generating(self, symbols: Sequence[str]) -> None:
        self._generating = list(symbols)
        self._refresh_recent()
        if self._generating:
            self._start_spinner()

    def add_generating(self, symbols: Sequence[str]) -> None:
        for sym in symbols:
            if sym not in self._generating:
                self._generating.append(sym)
        self._refresh_recent()
        if self._generating:
            self._start_spinner()

    def mark_done(self, run: ReportRun) -> None:
        if run.ticker in self._generating:
            self._generating.remove(run.ticker)
        self._recent = [r for r in self._recent if r.ticker != run.ticker]
        self._recent.insert(0, run)
        del self._recent[50:]
        self._refresh_recent()
        if not self._generating:
            self._stop_spinner()

    def remove_run(self, run: ReportRun) -> None:
        self._recent = [r for r in self._recent if r is not run]
        self._refresh_recent()

    def clear_generating(self, symbols: Sequence[str] | None = None) -> None:
        if symbols is None:
            self._generating = []
        else:
            drop = set(symbols)
            self._generating = [s for s in self._generating if s not in drop]
        if not self._generating:
            self._stop_spinner()
        self._refresh_recent()

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
        fields = {
            "report-interval": "interval_minutes",
            "report-timeout": "timeout_seconds",
            "report-concurrency": "max_concurrency",
        }
        attr = fields.get(event.input.id or "")
        if attr is None:
            return
        try:
            value = int(event.value)
        except ValueError:
            return
        setattr(self._settings, attr, value)
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
        elif bid.startswith("retry-"):
            try:
                idx = int(bid[len("retry-") :])
            except ValueError:
                return
            if 0 <= idx < len(self._recent):
                self._on_retry(self._recent[idx].ticker)
        elif bid.startswith("del-"):
            try:
                idx = int(bid[len("del-") :])
            except ValueError:
                return
            if 0 <= idx < len(self._recent):
                run = self._recent[idx]
                self._on_delete(run)
                self.remove_run(run)
