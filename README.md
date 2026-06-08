# gold-and-silver

Real-time terminal dashboard streaming live gold & silver prices with sparkline charts.
See [`CLAUDE.md`](CLAUDE.md) for architecture and the data-feed design.

## Run

```bash
uv sync
uv run goldsilver      # launch the TUI (quit with q)
```

## Hourly stock-analysis reports

An in-app engine generates self-contained HTML stock-analysis reports via the Claude CLI,
applying a Swedish-trader macro framework that **tests** its assumptions against today's
actual market reaction rather than asserting them.

- Press **`g`** in the TUI to open **Reports**: curate the watchlist (Gold & Silver are
  pinned), toggle hourly automation, **Generate now**, and open finished reports in your
  browser.
- Reports are written to `reports/<date>/<time>-<ticker>.html` (git-ignored) with a
  browsable `reports/index.html`.
- Headless / external scheduler:
  ```bash
  uv run python -m goldsilver.reports --all --once
  ```

Requires the `claude` CLI installed and logged in (subscription auth — no API key). Full
walkthrough: [`specs/003-hourly-stock-analyzer/quickstart.md`](specs/003-hourly-stock-analyzer/quickstart.md).

Advisory only — not financial advice.
