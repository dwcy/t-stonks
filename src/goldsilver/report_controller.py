"""Report UI controller: owns the run history, watchlist screen, and scheduler wiring."""

from __future__ import annotations

import asyncio
import webbrowser
from datetime import timedelta
from typing import TYPE_CHECKING

from goldsilver.reports.claude_runner import find_claude
from goldsilver.reports.html_writer import delete_report, load_recent_runs, write_index
from goldsilver.reports.models import ReportRun, ReportTicker
from goldsilver.reports.report_service import ReportService
from goldsilver.reports.scheduler import ReportScheduler
from goldsilver.reports.verdict_tracker import (
    evaluate_accuracy,
    fetch_daily_closes,
    yf_symbol_for_run,
)
from goldsilver.widgets import ReportUnavailableScreen, ReportWatchlistScreen

if TYPE_CHECKING:
    from goldsilver.app import GoldSilverApp


class ReportController:
    def __init__(self, app: GoldSilverApp) -> None:
        self._app = app
        self._service = ReportService(
            lambda: app._settings.report,
            on_run_complete=self._on_run_done,
        )
        self._runs: list[ReportRun] = load_recent_runs(self._service.out_root())
        self._scheduler: ReportScheduler | None = None
        self._screen: ReportWatchlistScreen | None = None

    def open_screen(self) -> None:
        if find_claude() is None:
            self._app.push_screen(ReportUnavailableScreen())
            return
        screen = ReportWatchlistScreen(
            self._app._settings.report,
            on_change=self._on_settings_change,
            on_generate=self.generate_all,
            on_open=self._open_run,
            on_retry=self.generate_one,
            on_delete=self._delete_run,
            recent=self._runs[:20],
            generating=sorted(self._service.in_flight()),
        )
        self._screen = screen
        self._app.push_screen(screen, self._on_screen_closed)
        self._app.run_worker(
            self._load_accuracy(),
            exclusive=True,
            group="report-accuracy",
        )

    async def _load_accuracy(self) -> None:
        runs = [r for r in self._runs if r.verdict is not None]
        if not runs:
            if self._screen is not None:
                self._screen.set_accuracy([])
            return
        start = min(r.started_at.date() for r in runs) - timedelta(days=5)
        symbols = {r.ticker: yf_symbol_for_run(r) for r in runs}
        closes = await asyncio.to_thread(fetch_daily_closes, symbols, start)
        rows = evaluate_accuracy(runs, closes)
        if self._screen is not None:
            self._screen.set_accuracy(rows)

    def start_scheduler_if_enabled(self) -> None:
        if self._app._settings.report.enabled:
            self._start_scheduler()

    def request_stop(self) -> None:
        if self._scheduler is not None:
            self._scheduler.request_stop()

    def generate_all(self) -> None:
        self._run_reports(self._service.effective_watchlist(), replace=True)

    def generate_one(self, symbol: str) -> None:
        self._run_reports(self._service.resolve_tickers([symbol]), replace=False)

    def _on_screen_closed(self, _result: None) -> None:
        self._screen = None

    def _on_settings_change(self) -> None:
        self._app._persist_settings()
        if self._app._settings.report.enabled and self._scheduler is None:
            self._start_scheduler()
        elif not self._app._settings.report.enabled and self._scheduler is not None:
            self._scheduler.request_stop()
            self._scheduler = None

    def _start_scheduler(self) -> None:
        if self._scheduler is not None:
            return
        scheduler = ReportScheduler(
            self._service,
            enabled=lambda: self._app._settings.report.enabled,
            interval_minutes=lambda: self._app._settings.report.interval_minutes,
            on_error=lambda msg: self._app.notify(msg, severity="error", timeout=8),
        )
        self._scheduler = scheduler
        self._app.run_worker(
            scheduler.run_loop(),
            exclusive=True,
            group="report-scheduler",
        )

    def _run_reports(self, tickers: list[ReportTicker], *, replace: bool) -> None:
        symbols = [t.symbol for t in tickers]
        if self._screen is not None:
            if replace:
                self._screen.mark_generating(symbols)
            else:
                self._screen.add_generating(symbols)
        self._app.run_worker(
            self._generate(list(tickers), symbols),
            exclusive=False,
            group="report-generate",
        )

    async def _generate(self, tickers: list[ReportTicker], symbols: list[str]) -> None:
        self._app.notify(f"Generating {len(symbols)} report(s)…", timeout=3)
        runs = await self._service.run_all(tickers)
        if self._screen is not None:
            self._screen.clear_generating(symbols)
        ok = sum(1 for r in runs if r.html_path)
        self._app.notify(f"Reports done: {ok}/{len(runs)}", timeout=5)

    def _on_run_done(self, run: ReportRun) -> None:
        self._runs = [r for r in self._runs if r.ticker != run.ticker]
        self._runs.insert(0, run)
        del self._runs[50:]
        if self._screen is not None:
            self._screen.mark_done(run)

    def _delete_run(self, run: ReportRun) -> None:
        root = self._service.out_root()
        delete_report(root, run.html_path)
        self._runs = [r for r in self._runs if r is not run]
        write_index(root)

    def _open_run(self, run: ReportRun) -> None:
        if not run.html_path:
            return
        path = self._service.out_root() / run.html_path
        try:
            webbrowser.open(path.resolve().as_uri())
        except OSError:
            self._app.notify("Could not open report", severity="error", timeout=5)
