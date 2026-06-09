"""Headless report runner: `python -m goldsilver.reports [--all|--ticker X] [--once]`."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from goldsilver.data.settings import AppSettings
from goldsilver.reports.models import ReportRun, ReportStatus
from goldsilver.reports.report_service import ReportService

_FAIL_STATUSES = {ReportStatus.TIMEOUT, ReportStatus.ERROR, ReportStatus.CLI_MISSING}


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="python -m goldsilver.reports")
    p.add_argument("--ticker", action="append", default=[], metavar="SYM")
    p.add_argument("--all", action="store_true")
    p.add_argument("--once", action="store_true")
    p.add_argument("--out", default=None)
    p.add_argument("--timeout", type=int, default=None)
    p.add_argument("--concurrency", type=int, default=None)
    p.add_argument("--no-index", action="store_true")
    p.add_argument("--json", action="store_true")
    return p.parse_args(argv)


def _format_line(run: ReportRun) -> str:
    mark = "✓" if run.status in (ReportStatus.SUCCESS, ReportStatus.MALFORMED) else "✗"
    if run.verdict is not None:
        call = f"{run.verdict.intraday}/{run.verdict.swing} {run.verdict.confidence}%"
    else:
        call = run.status.value
    where = run.html_path or run.error or ""
    return f"{mark} {run.ticker:<8} {call:<16} {where}"


def _exit_code(runs: list[ReportRun]) -> int:
    if not runs:
        return 2
    statuses = [r.status for r in runs]
    if all(s is ReportStatus.CLI_MISSING for s in statuses):
        return 3
    if any(s in _FAIL_STATUSES for s in statuses):
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    settings = AppSettings.load()
    if args.out is not None:
        settings.report.out_dir = args.out
    if args.timeout is not None:
        settings.report.timeout_seconds = args.timeout
    settings.report.__post_init__()

    service = ReportService(lambda: settings.report)
    root = service.out_root()
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"error: cannot write to {root}: {exc}", file=sys.stderr)
        return 4

    if args.ticker:
        tickers = service.resolve_tickers(args.ticker)
    else:
        tickers = service.effective_watchlist()

    runs = asyncio.run(
        service.run_all(
            tickers,
            concurrency=args.concurrency,
            regenerate_index=not args.no_index,
        )
    )

    if args.json:
        payload = "[" + ",".join(r.model_dump_json() for r in runs) + "]"
        print(payload)
    else:
        for run in runs:
            print(_format_line(run))
    return _exit_code(runs)


if __name__ == "__main__":
    raise SystemExit(main())
