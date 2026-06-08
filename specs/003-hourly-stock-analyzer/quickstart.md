# Quickstart: Hourly Stock-Analysis Reports

How the feature works once implemented, for the operator and the next developer.

## Prerequisites

- The `claude` CLI installed, logged in (subscription auth), and on `PATH`. Verify:
  ```
  claude --version
  ```
  No `ANTHROPIC_API_KEY` is needed — the engine uses the CLI login.
- Internet access (the CLI fetches live market data via its web tools).
- `uv sync` (no new third-party deps are added — scheduling is stdlib `asyncio`).

## Operator flow (in the TUI)

1. `uv run goldsilver` to launch the dashboard.
2. Press the **watchlist key** (e.g. `R`) to open the report watchlist editor.
3. Add stock tickers (e.g. `NVDA`, `VOLV-B.ST`); remove ones you don't want. **Gold** and
   **Silver** are pinned and always analyzed.
4. Toggle **Enable hourly reports** on. The scheduler now fires at the top of each hour
   while the app runs.
5. Press **Generate now** to produce reports immediately. When each finishes, a clickable
   link appears; activate it to open the report in your browser.
6. Browse history any time via `reports/index.html`.

## Where reports land

```
reports/
├── index.html                      # browse-all page, newest first
└── 2026-06-08/
    ├── 14-00-XAU.html  + .json     # Gold, 14:00 Stockholm
    ├── 14-00-XAG.html  + .json     # Silver
    └── 14-00-NVDA.html + .json
```

`reports/` is git-ignored.

## Headless / external scheduler (optional)

The same pipeline runs without the TUI — useful for Windows Task Scheduler or cron:

```
# whole watchlist, one pass
python -m goldsilver.reports --all --once

# specific instruments
python -m goldsilver.reports --ticker XAU --ticker NVDA --once

# machine-readable summary
python -m goldsilver.reports --all --once --json
```

Exit codes: `0` all good · `2` some ticker failed · `3` `claude` not found · `4` bad args.

Windows Task Scheduler (hourly) example:
```
schtasks /Create /SC HOURLY /TN goldsilver-reports ^
  /TR "uv run python -m goldsilver.reports --all --once" /ST 09:00
```
Linux cron:
```
0 * * * * cd /path/to/gold-and-silver && uv run python -m goldsilver.reports --all --once
```

## What's in a report

Each report applies the Swedish-trader framework (see
`contracts/analysis-prompt.md`). Its defining trait: it **tests** macro assumptions
against today's real price action instead of asserting them, flags broken correlations,
and ends with a fixed verdict block — intraday + swing BUY/HOLD/SELL, confidence, and
per-driver Positive/Neutral/Negative impacts.

## Config (persisted in settings.json)

New `report` section under `AppSettings`:
```jsonc
"report": {
  "enabled": false,                 // hourly scheduler off until you opt in
  "interval_minutes": 60,
  "report_tickers": ["NVDA"],       // stocks; metals are pinned in code
  "timeout_seconds": 180,
  "max_concurrency": 3,             // simultaneous claude processes; 1 = sequential
  "allowed_tools": ["WebSearch", "WebFetch", "Read"],
  "out_dir": "reports"
}
```

## Tests to run after implementation

```
uv run pytest tests/test_report_phase.py tests/test_prompt_builder.py \
  tests/test_claude_runner.py tests/test_html_writer.py tests/test_report_watchlist.py
```
`claude` is mocked in `test_claude_runner.py` (no live CLI call in CI).

## Safety

Advisory only — **not financial advice**. The engine never places trades and never
touches the trade simulator; the CLI is granted web/read tools only (no `Write`/`Bash`).
