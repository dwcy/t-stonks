# Contract: Headless Report Runner

`python -m goldsilver.reports` — drives the same run path as the in-app scheduler, for
one-shot/external-scheduler use (FR-008). Exit code communicates aggregate status.

## Invocation

```
python -m goldsilver.reports [--ticker SYM ... | --all] [--once] [--out DIR]
                             [--timeout SECONDS] [--no-index] [--json]
```

| Flag | Default | Meaning |
|---|---|---|
| `--all` | (default if no `--ticker`) | Run the effective watchlist (pinned metals + `report_tickers` from settings). |
| `--ticker SYM` | — | Run a specific symbol; repeatable. Bypasses the saved watchlist. Metals (`XAU`/`XAG`) accepted. |
| `--once` | implied | Run exactly one pass and exit (the only mode for the CLI; named for parity with a daemon). |
| `--out DIR` | `settings.out_dir` (`reports`) | Output root, relative to repo root. |
| `--timeout SECONDS` | `settings.timeout_seconds` (180) | Per-ticker CLI timeout. |
| `--no-index` | off | Skip `index.html` regeneration. |
| `--json` | off | Emit a machine-readable run summary to stdout (array of `ReportRun`). |

## Behavior

- Resolves the effective watchlist, runs each ticker **sequentially** (avoid spawning N
  concurrent `claude` processes on a personal machine; concurrency is a future knob).
- Each ticker writes `reports/<date>/<HH-MM>-<TICKER>.html` + sidecar `.json`
  (report-file contract).
- A single ticker failure never aborts the batch (FR-018); its `ReportRun` records the
  failure status.
- Regenerates `reports/index.html` at the end unless `--no-index`.

## Output

- Human mode: one line per ticker — `✓ XAU  BUY/HOLD  82%  reports/2026-06-08/14-00-XAU.html`
  or `✗ NVDA  TIMEOUT  (180s)`.
- `--json` mode: JSON array of serialized `ReportRun` to stdout (logs to stderr).

## Exit codes

| Code | Condition |
|---|---|
| `0` | All tickers produced a valid report (`SUCCESS`/`MALFORMED` with file written). |
| `2` | At least one ticker failed (`TIMEOUT`/`ERROR`). |
| `3` | `claude` CLI not found on PATH (`CLI_MISSING` for all). |
| `4` | Bad arguments / unwritable `--out`. |

## Non-goals

- The CLI does **not** loop/daemonize. Hourly cadence in headless mode is the host
  scheduler's job (Task Scheduler / cron calling `--once`); the in-app scheduler covers
  the running-TUI case.
