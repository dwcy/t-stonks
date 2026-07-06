# Implementation Plan: Shared `marketcore` Layer + `quantum` App

**Branch**: `004-shared-core-quantum-app` | **Date**: 2026-06-27 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/004-shared-core-quantum-app/spec.md`

## Summary

Introduce a lower-layer Python package `marketcore` that owns the symbol-agnostic
foundation already present in `goldsilver` (models, HTTP factory, session/timezone
helpers, the polling-service base, generic data services, the strategy/backtest/trade
engine, the Claude report engine, and generic Textual widgets). `goldsilver` is
re-pointed to import from `marketcore` and keeps only the metal-specific slice. A new
`quantum` app is built on `marketcore` to track quantum ETFs (headline tiles),
pure-play quantum stocks (reused `StockService`), and a quantum news feed (reused news
service with an injected feed list). Both apps run via their own `uv run` console
scripts and isolate their on-disk config by app name.

Technical approach: **relocate-and-reimport**, not rewrite. The exploration confirmed
most services are already callback-based and symbol-agnostic; the only true
parameterization work is (a) extracting a `PollingService` base from `MetalsService`,
(b) turning the hardcoded `NEWS_FEEDS` constant into an injected list, and (c) adding
an `app_name` parameter to the config-base path helper. Everything else is a module
move plus an import-path fix, guarded by the existing test suite.

## Technical Context

**Language/Version**: Python 3.12+ (unchanged)
**Primary Dependencies**: Textual 8.2.7+, textual-plotext 1.0.1+, httpx 0.28.1+, pydantic 2.13.4+, yfinance 1.4.0+ (no new deps)
**Storage**: Local JSON config under per-app OS config dir (`%APPDATA%\<app>` / `$XDG_CONFIG_HOME/<app>`); report HTML on disk. No DB.
**Testing**: pytest + pytest-asyncio (`asyncio_mode = "auto"`), Textual `run_test()`/`Pilot` for widget smoke tests
**Target Platform**: Cross-platform terminal (Linux-primary, Windows Terminal supported)
**Project Type**: Multi-app monorepo — one repo, one `pyproject.toml`, three packages (`marketcore` library + `goldsilver`/`quantum` apps), multiple console scripts
**Performance Goals**: Unchanged — TUI stays responsive; all I/O async in Textual workers; poll cadences unchanged (live 5s, slow feeds 30–60s)
**Constraints**: Single process per app; no backend/server/DB; no API keys; `marketcore` must not import any app package; respect Python LoC budgets on moved/new files
**Scale/Scope**: ~5,500 LoC relocated into `marketcore`; ~1,500 LoC stays in `goldsilver`; ~600–900 LoC new for `quantum`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The project constitution at `.specify/memory/constitution.md` is an unfilled template
(placeholder principles only), so there are no ratified numeric gates to enforce. In
its place this plan is held to the standing project + global rules:

| Rule | Status |
|------|--------|
| No backend / server / persistence layer beyond local JSON (project CLAUDE.md) | PASS — apps stay single-process TUIs; no new persistence tier |
| Pydantic models for any data crossing a boundary | PASS — reuses existing `Tick`/`Bar`/macro models; no `.get()` chains added |
| Async-first; no blocking I/O on the event loop | PASS — only relocating already-async services |
| Hybrid feed integrity for gold/silver not collapsed | PASS — `MetalsService` (goldprice.org + Avanza hybrid) stays intact in `goldsilver` |
| Latest stable deps, no deprecated APIs | PASS — no dependency changes |
| Python file LoC budgets (`rules/python.md`) | PASS by design — splits called out in Project Structure where a move would breach a cap |
| `from __future__ import annotations`, `pathlib`, no `import *`, module docstrings | PASS — applied to new `marketcore`/`quantum` modules |

**Result**: No violations. Complexity Tracking table left empty.

## Project Structure

### Documentation (this feature)

```text
specs/004-shared-core-quantum-app/
├── plan.md              # This file
├── spec.md              # Feature spec (anchor for this plan)
├── research.md          # Phase 0 — extraction strategy + quantum data sources
├── data-model.md        # Phase 1 — entities, config/preset shapes, ticker/feed sets
├── quickstart.md        # Phase 1 — how to run both apps + add a third
├── contracts/
│   ├── marketcore-public-api.md   # The stable import surface marketcore exposes
│   ├── quantum-app-cli.md         # `uv run quantum` command + UI contract
│   └── app-config-isolation.md    # Per-app config-base + feed-injection contract
└── tasks.md             # Phase 2 — produced by /speckit-tasks (NOT this command)
```

### Source Code (repository root)

Target layout after this feature (multi-package `src/`, single `pyproject.toml`):

```text
src/
├── marketcore/                 # NEW shared lower layer (no app imports)
│   ├── __init__.py             # curated public exports
│   ├── models.py               # Tick, Bar  (moved from goldsilver/data/models.py minus GOLD/SILVER)
│   ├── models_macro.py         # Fx/Commodity/Stock/News/Signal/etc. (moved as-is)
│   ├── http.py                 # make_client()  (moved)
│   ├── session.py              # tz-parameterized now/date/midnight helpers
│   ├── paths.py                # config_base(app_name) + per-app path builders (NEW, from settings.py:506-517)
│   ├── fsutil.py               # atomic_write_text() (moved)
│   ├── strategies/
│   │   ├── signal_strategies.py
│   │   ├── alerts.py
│   │   └── backtest.py
│   ├── trade_models.py
│   ├── services/
│   │   ├── base.py             # PollingService (NEW — extracted from MetalsService + _FeedService shape)
│   │   ├── stock_service.py    # StockService (already generic)
│   │   ├── news_service.py     # _FeedService + NewsService(feeds=...) — feed list now injected
│   │   ├── fx_service.py
│   │   ├── commodity_service.py
│   │   ├── futures_service.py
│   │   ├── yields_service.py
│   │   ├── calendar_service.py
│   │   └── … (insider/congress/stocktwits/omx as-moved)
│   ├── reports/                # claude_runner, report_service, html_writer, scheduler, verdict_tracker, reference_quote, models (locale phases parameterized)
│   └── widgets/
│       ├── chart.py            # PriceChart (generic)
│       ├── stock_tile.py
│       ├── fx_tile.py
│       ├── commodity_tile.py
│       └── ratio_tile.py       # thresholds parameterized
│
├── goldsilver/                 # EXISTING app — re-pointed to marketcore
│   ├── __init__.py             # exposes main()
│   ├── __main__.py
│   ├── app.py                  # GoldSilverApp (imports marketcore.*)
│   ├── report_controller.py
│   ├── settings_sync.py
│   ├── data/
│   │   ├── service.py          # MetalsService(PollingService) — metal endpoints/orderbooks
│   │   ├── settings.py         # AppSettings + metal presets; paths via marketcore.paths(app_name="goldsilver")
│   │   ├── news_feeds.py       # goldsilver NEWS_FEEDS list passed into NewsService
│   │   └── stock_presets.py    # mining/metal ticker presets
│   ├── reports/
│   │   ├── prompt_builder.py   # metal analysis prompt
│   │   └── constants.py        # METAL_LABELS, pinned metals
│   ├── widgets/
│   │   ├── metal_panel.py      # MetalPanel + strategy label dict
│   │   └── … (calendar/news/congress/insider screens that stay app-coupled)
│   └── styles/app.tcss
│
└── quantum/                    # NEW app on marketcore
    ├── __init__.py             # exposes main()
    ├── __main__.py
    ├── app.py                  # QuantumApp
    ├── data/
    │   ├── settings.py         # QuantumSettings; paths via marketcore.paths(app_name="quantum")
    │   ├── news_feeds.py       # quantum news feed list
    │   └── presets.py          # ETF + pure-play ticker sets, accent colours
    └── styles/app.tcss

tests/
├── (existing goldsilver tests — pass post-move)
├── marketcore/                 # new: paths(app_name), news feed injection, PollingService
└── quantum/                    # new: app mount+render smoke test, preset wiring
```

**Structure Decision**: Single `pyproject.toml` with a `src/` containing three packages
and two `[project.scripts]` entries (`goldsilver`, `quantum`). The `uv_build` backend
discovers all top-level packages under `src/`. This keeps one lockfile, one venv, one
`uv sync`, and lets `marketcore` be imported by both apps without packaging it
separately. The repo distribution name stays `goldsilver` for now (renaming the
distribution is out of scope); the importable packages are what matter.

## Phasing & Sequencing (implementation strategy)

Ordered to keep the suite green at every step:

1. **Scaffold `marketcore`** — create package skeleton + `__init__.py`. No behaviour yet.
2. **Move leaf modules** (no internal deps): `http.py`, `fsutil.py`, `models.py`
   (drop `GOLD`/`SILVER` → keep them in `goldsilver/data/models.py` as a thin shim
   re-exporting `Tick`/`Bar`), `models_macro.py`, `session.py` (add `tz` param).
   Re-point `goldsilver` imports; run tests.
3. **Extract `paths.py`** — `config_base(app_name)` + path builders; `goldsilver`
   `settings.py` calls them with `"goldsilver"`. Verify config path unchanged.
4. **Move service layer** — relocate generic services; extract `PollingService` base;
   convert `NewsService` to take an injected feed list (`goldsilver` passes its
   existing `NEWS_FEEDS`). Re-point imports; run tests.
5. **Move strategy/trade/report/widget layers** — relocate; fix imports; parameterize
   `ratio_tile` thresholds and report locale phases. Run full suite.
6. **`MetalsService` rebinds onto `PollingService`** — keep goldprice.org + Avanza
   hybrid intact; confirm `goldsilver` UI unchanged via `/run`.
7. **Build `quantum`** — presets, settings, news feeds, `app.py`, console script.
8. **Tests + docs** — `marketcore` unit tests, `quantum` smoke test, update READMEs.

> Detailed, dependency-ordered tasks are produced by `/speckit-tasks` into `tasks.md`.

## Complexity Tracking

> No constitution violations — table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
