# Feature Specification: Shared `marketcore` Layer + `quantum` App

**Branch**: `004-shared-core-quantum-app` | **Date**: 2026-06-27
**Status**: Draft

## Summary

Extract the genuinely reusable infrastructure currently living inside the
`goldsilver` package into a new lower-layer package, `marketcore`, so that
multiple terminal dashboards can be built on top of one shared foundation.
Prove the layering by adding a second app, `quantum` (`uv run quantum`), that
tracks top quantum-computing ETFs and pure-play quantum stocks plus a
quantum-computing news feed — reusing `marketcore` for ~90% of its machinery.

The existing `goldsilver` app must keep working unchanged (`uv run goldsilver`,
same behaviour, same on-disk config location).

## Background

`goldsilver` has grown to ~7,000 LoC. The bulk of it is already symbol-agnostic:
polling-service scaffolding, generic data services (stocks, FX, commodities,
news, calendar, congress, insider, social), a Pydantic model layer, a signal /
strategy engine, a backtest + trade simulator, an AI report engine (Claude CLI),
and a set of reusable Textual widgets (chart, tiles). Only a thin slice is truly
gold/silver-specific: `MetalsService` (goldprice.org + Avanza orderbook IDs +
GC=F/SI=F), the metal report prompt, the metal colour presets, `MetalPanel`, and
`app.py` wiring. This feature draws the line between the two.

## User Scenarios

### Scenario 1 — Existing user keeps the gold/silver app
A current `goldsilver` user upgrades, runs `uv run goldsilver`, and sees the
exact same dashboard with the same settings (read from the same config path).
Nothing about their experience changes.

### Scenario 2 — Launch the quantum dashboard
A user runs `uv run quantum`. A Textual TUI opens showing:
- Headline live tiles for quantum ETFs (e.g. `QTUM`, `QBTS`-style ETF set).
- A panel of pure-play quantum stocks (e.g. `IONQ`, `RGTI`, `QUBT`, `QBTS`,
  `ARQQ`) with live quote, change %, and mini sparkline.
- A scrolling quantum-computing news feed.
The app quits with `q`. Its settings persist to a `quantum`-specific config
location, independent of `goldsilver`.

### Scenario 3 — A developer adds a third app later
A developer can scaffold a new dashboard by importing `marketcore` services and
widgets and writing only an app-specific `app.py`, settings presets, and (if
needed) a bespoke data service — without copying code out of `goldsilver`.

## Functional Requirements

- **FR-1 — `marketcore` package exists.** A new `src/marketcore/` package holds
  the reusable foundation: models, HTTP factory, timezone/session helpers,
  polling-service base, generic data services, strategy engine, backtest/trade
  models, report engine, and generic widgets. It has no import dependency on
  `goldsilver` or `quantum`.

- **FR-2 — `goldsilver` consumes `marketcore`.** `goldsilver` imports shared
  code from `marketcore` instead of defining it locally. Remaining `goldsilver`
  modules are only the metal-specific slice (`MetalsService`, metal prompt
  builder, metal colour presets, `MetalPanel`, `app.py`, app wiring).

- **FR-3 — No behavioural change to `goldsilver`.** `uv run goldsilver` produces
  the same UI and reads/writes settings at the same path as before this feature.

- **FR-4 — Parameterized config location.** The config-base helper that currently
  hardcodes the `goldsilver` directory segment takes an app-name parameter so
  each app isolates its own `settings.json` / `trades.json` / report output.
  `goldsilver` continues to use the `goldsilver` segment (no migration of
  existing files).

- **FR-5 — Parameterized news feeds.** The news service accepts its feed list as
  a parameter (today `NEWS_FEEDS` is a module constant). `goldsilver` passes its
  existing feeds; `quantum` passes a quantum-computing feed set.

- **FR-6 — `quantum` app + entry point.** A new `src/quantum/` package provides a
  Textual app and a `quantum = "quantum:main"` console script registered in
  `pyproject.toml`, runnable via `uv run quantum`.

- **FR-7 — Quantum data wiring.** `quantum` tracks: a configurable set of quantum
  ETFs as headline tiles, a configurable set of pure-play quantum stocks via the
  reused `StockService`, and a quantum news feed via the reused news service.
  Default ticker/feed sets ship as `quantum`-specific presets.

- **FR-8 — Quantum settings isolation.** `quantum` persists its settings under a
  `quantum` config segment (per FR-4), with its own default ticker/feed/colour
  presets.

- **FR-9 — Tests pass for both apps.** Existing `goldsilver` tests pass against
  the refactored layout; new tests cover the `marketcore` public surface that was
  parameterized (config-base app-name, news-feed injection) and a `quantum`
  app smoke test (mount + render).

## Non-Functional Requirements

- **Reuse over rewrite.** Move-and-reimport; do not rewrite working logic. Keep
  diffs mechanical where possible (relocate module, fix imports).
- **Latest stable deps.** No new heavy dependencies; reuse `httpx`, `pydantic`,
  `textual`, `textual-plotext`, `yfinance`. No API keys.
- **Single process per app.** No backend/server/DB — each app stays a
  single-process TUI (per project constitution).
- **File-size discipline.** New/moved modules respect the Python LoC budgets;
  split where a relocation would breach a cap.

## Out of Scope

- Full extraction of *every* generic module (settings base internals, trade
  simulator UI, every niche service) — this feature does **foundation-level**
  extraction (the clearly-shared core + what `quantum` needs), not a total
  teardown. Deeper extraction can follow incrementally.
- Migrating existing `goldsilver` user config files to a new location.
- A plugin/registry system for auto-discovering apps.
- Packaging/publishing `marketcore` as a separate distributable on PyPI.

## Success Criteria

- `uv run goldsilver` works identically to pre-feature behaviour.
- `uv run quantum` launches a working ETF + stocks + news dashboard.
- `marketcore` has zero imports of `goldsilver`/`quantum`.
- `uv run pytest` is green.

## Key Entities

- **App** — a runnable Textual dashboard (`goldsilver`, `quantum`) with its own
  symbols, presets, layout, and config segment.
- **Shared service** — a `marketcore` polling service reused across apps.
- **Quantum instrument set** — the ETF tickers, pure-play stock tickers, and
  news feeds that define the `quantum` app's domain.

## Clarifications Resolved

- Core package name: **`marketcore`**.
- Quantum scope: **ETF tiles + pure-play stock panel + news feed**.
- Extraction depth: **Foundation extraction** (shared core + quantum needs;
  metal-specific code stays in `goldsilver`).
