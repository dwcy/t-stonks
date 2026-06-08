"""Orchestrate report runs: build context, run the CLI in bounded parallel, write files."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path

from goldsilver.data.session import STOCKHOLM, stockholm_now
from goldsilver.data.settings import ReportSettings
from goldsilver.reports.claude_runner import run_claude
from goldsilver.reports.html_writer import prune_ticker, write_index, write_report
from goldsilver.reports.models import (
    ReportRun,
    ReportStatus,
    ReportTicker,
    pinned_metal_tickers,
)
from goldsilver.reports.prompt_builder import AnalysisPromptContext, build_prompt

RunCallback = Callable[[ReportRun], None]
SettingsProvider = Callable[[], ReportSettings]


class ReportService:
    def __init__(
        self,
        settings_provider: SettingsProvider,
        *,
        on_run_complete: RunCallback | None = None,
        claude_path: str | None = None,
    ) -> None:
        self._settings_provider = settings_provider
        self._on_run_complete = on_run_complete
        self._claude_path = claude_path
        self._inflight: set[str] = set()

    def in_flight(self) -> set[str]:
        return set(self._inflight)

    def out_root(self) -> Path:
        return Path.cwd() / self._settings_provider().out_dir

    def effective_watchlist(self) -> list[ReportTicker]:
        stocks = [
            ReportTicker.stock(sym) for sym in self._settings_provider().report_tickers
        ]
        return pinned_metal_tickers() + stocks

    def resolve_tickers(self, symbols: Sequence[str]) -> list[ReportTicker]:
        watchlist = {t.symbol: t for t in self.effective_watchlist()}
        out: list[ReportTicker] = []
        for raw in symbols:
            sym = raw.strip().upper()
            out.append(watchlist.get(sym) or ReportTicker.stock(sym))
        return out

    async def run_one(
        self,
        ticker: ReportTicker,
        *,
        out_root: Path | None = None,
        now: datetime | None = None,
    ) -> ReportRun | None:
        if ticker.symbol in self._inflight:
            return None
        self._inflight.add(ticker.symbol)
        try:
            settings = self._settings_provider()
            root = out_root if out_root is not None else self.out_root()
            started = (now or stockholm_now()).astimezone(STOCKHOLM)
            run = ReportRun(
                ticker=ticker.symbol,
                label=ticker.label,
                kind=ticker.kind,
                started_at=started,
                status=ReportStatus.RUNNING,
            )
            context = AnalysisPromptContext.for_ticker(ticker, started)
            prompt = build_prompt(context)
            result = await run_claude(
                prompt,
                allowed_tools=list(settings.allowed_tools),
                timeout_seconds=settings.timeout_seconds,
                claude_path=self._claude_path,
            )
            run.status = result.status
            run.verdict = result.verdict
            run.error = result.error
            finished = stockholm_now().astimezone(STOCKHOLM)
            run.finished_at = finished
            run.duration_seconds = (finished - started).total_seconds()
            run = write_report(root, run, result.html)
            if run.status is ReportStatus.SUCCESS:
                prune_ticker(root, ticker.symbol, run.html_path)
            if self._on_run_complete is not None:
                self._on_run_complete(run)
            return run
        finally:
            self._inflight.discard(ticker.symbol)

    async def run_all(
        self,
        tickers: Sequence[ReportTicker] | None = None,
        *,
        concurrency: int | None = None,
        regenerate_index: bool = True,
    ) -> list[ReportRun]:
        settings = self._settings_provider()
        watchlist = list(tickers) if tickers is not None else self.effective_watchlist()
        root = self.out_root()
        limit = concurrency if concurrency is not None else settings.max_concurrency
        sem = asyncio.Semaphore(max(1, limit))

        async def _guarded(t: ReportTicker) -> ReportRun | None:
            async with sem:
                return await self.run_one(t, out_root=root)

        results = await asyncio.gather(
            *(_guarded(t) for t in watchlist), return_exceptions=True
        )
        runs = [r for r in results if isinstance(r, ReportRun)]
        if regenerate_index:
            write_index(root)
        return runs
