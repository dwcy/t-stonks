# Implementation Plan: Dashboard UX & Data-Quality Fixes

**Branch**: `005-dashboard-ux-fixes` | **Date**: 2026-07-10 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/005-dashboard-ux-fixes/spec.md`

## Summary

Ten independently-shippable stories bundled into one feature branch: fix news-feed
timestamp honesty and add a browsable news log; add a "read more" link; add
click-to-reveal descriptions + a fixed priority order for the six signal indicators;
show a spinner during the macro calendar's existing auto-fetch-after-event-time
mechanism; replace ticker shorthand ("Au", "DXY", report tickers) with readable names
in the remaining places that leak them; extend AI report generation to copper and
oil; add live USA/Sweden policy interest rate tiles; add DAX/CAC 40/FTSE 100/Nikkei
225 index tiles; add a click-to-open full chart modal for any stock tile's mini
sparkline, with a 40-day up/down history strip; and surface report-watchlist status
plus dividend info inside that same modal.

Technical approach: **extend existing patterns, introduce no new architecture.**
Every story maps onto a pattern this codebase already has — `PollingService`-shaped
services for new live data (rates, indices), the `ModalScreen` push/dismiss pattern
already used for calendar-event detail (chart modal, news log), the meta-click-span
technique already used by the calendar panel (news read-more, indicator descriptions),
and `PriceChart`'s existing external-feed contract (`seed()`/`add_point()`) for the
new chart modal. The one net-new integration is Sweden's Riksbank REST API (no FRED
equivalent exists for the actual policy rate); everything else reuses `httpx`,
`yfinance`, or FRED, already dependencies of this project.

## Technical Context

**Language/Version**: Python 3.12+ (unchanged)
**Primary Dependencies**: Textual 8.2.7+, textual-plotext 1.0.1+, httpx 0.28.1+, pydantic 2.13.4+, yfinance 1.4.0+ (no new deps — Riksbank's REST API is plain JSON over the existing `httpx` client)
**Storage**: Local JSON config under per-app OS config dir (unchanged); report HTML/JSON sidecars on disk (unchanged, extended to copper/oil); news log is in-memory only (no new storage)
**Testing**: pytest + pytest-asyncio (`asyncio_mode = "auto"`), Textual `run_test()`/`Pilot` for widget smoke tests
**Target Platform**: Cross-platform terminal (Linux-primary, Windows Terminal supported)
**Project Type**: Multi-app monorepo (existing `marketcore` + `goldsilver` + `quantum`) — this feature adds to `marketcore` (shared models/services touched by both apps) and `goldsilver` (all ten stories are goldsilver-dashboard-scoped; Story 9's chart-modal trigger also wires into `quantum` since it reuses `marketcore.StockTile`)
**Performance Goals**: Unchanged — new poll loops (rates, indices) run on slow cadences (4h for rates, matching existing tile refresh cadences for indices); chart-modal fetches are one-shot per open, not polled
**Constraints**: No backend/server/DB; no new required API keys beyond the already-existing `GOLDSILVER_FRED_KEY` (Riksbank's API needs no key for this app's request volume); `marketcore` must not import `goldsilver`/`quantum`; new Textual screens respect the 250-soft/400-hard LoC caps in `rules/python.md`
**Scale/Scope**: ~10 new small modules (services + 2 new widgets + 2 new modal screens), ~15 existing files touched with targeted changes (see Project Structure); no existing module needs a structural split as a result of these changes

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md` is an unfilled template (no ratified project-specific
gates). This plan is held to the standing project + global rules instead:

| Rule | Status |
|---|---|
| No backend / server / persistence layer beyond local JSON (project `CLAUDE.md`) | PASS — news log is in-memory; everything else uses the app's existing settings-JSON / report-sidecar persistence |
| Don't drop either feed of the gold/silver hybrid without thinking through the tradeoff | PASS — untouched; Story 7's Sweden-rate decision explicitly follows the same "don't collapse to a convenient-but-wrong single source" reasoning (R8) |
| Pydantic models for any data crossing a boundary | PASS — new `RatePoint`, `IndexPoint`, `DailyChange`, `DividendInfo` models for every new external response; no `.get()` chains |
| Reactive widgets — no manual `refresh()` from outside | PASS — new tiles (`RateTile`, `IndexTile`) and the chart modal follow the existing `reactive` + `watch_*` pattern already used by `CommodityTile`/`RealYieldTile` |
| Async-first — all I/O in Textual workers | PASS — new FRED/Riksbank/yfinance calls are async via the existing `httpx.AsyncClient`/`make_client()` factory or `yfinance`'s already-in-use sync calls wrapped the same way `stock_service.py` wraps them today |
| Latest stable deps, no deprecated APIs | PASS — no new dependencies |
| Python file LoC budgets (`rules/python.md`) | PASS — new service modules are small (single-responsibility fetch+parse, mirroring `yields_service.py`'s ~120 LoC shape); `StockChartScreen` is the largest new file and stays under the 250 soft cap by delegating fetch orchestration to `stock_service.py` functions rather than doing I/O inline (see `research.md` cross-cutting notes) |
| `from __future__ import annotations`, `pathlib`, no `import *`, module docstrings | PASS — applied to all new modules |
| Textual widget naming (no shadowing `_render`/`_compose`/etc.) | PASS — new widgets use role-based helper names (`_redraw`, `_build_rows`) matching existing conventions; enforced by the repo's pre-commit hook regardless |

**Result**: No violations. Complexity Tracking table left empty.

## Project Structure

### Documentation (this feature)

```text
specs/005-dashboard-ux-fixes/
├── plan.md                          # This file
├── spec.md                          # Feature spec (anchor for this plan)
├── research.md                      # Phase 0 — 11 research items, one per story/sub-decision
├── data-model.md                    # Phase 1 — new/changed entities
├── quickstart.md                    # Phase 1 — manual verification steps per story
├── contracts/
│   ├── mini-tile-registry.md        # Story 7/8 — how new tiles plug into ALLOWED_MINI_TILES
│   ├── chart-detail-modal.md        # Story 9/10 — StockChartScreen inputs/composition
│   └── click-region-interactions.md # Story 2/3/4 — shared meta-click-span convention
└── tasks.md                         # Phase 2 — produced by /speckit-tasks (NOT this command)
```

### Source Code (repository root)

```text
src/
├── marketcore/
│   ├── models.py                    # CHANGED — add DailyChange
│   ├── models_macro.py              # CHANGED — NewsItem.time_confidence; add RatePoint, IndexPoint, DividendInfo
│   ├── services/
│   │   ├── news_service.py          # CHANGED — time_confidence tagging (R1) + bounded history deque (R2)
│   │   └── stock_service.py         # CHANGED — add fetch_daily_history(), fetch_dividend_info()
│   └── widgets/
│       └── stock_tile.py            # CHANGED — _StockSpark.on_click → forwards ticker to owning app
│
├── goldsilver/
│   ├── app.py                       # CHANGED — wire new services (start/stop), new mini-tile dispatch branches, _show_stock_chart(), news-log open action
│   ├── report_controller.py         # CHANGED — expose a by-ticker lookup over self._runs for the chart modal
│   ├── data/
│   │   ├── fred.py                  # NEW — shared FRED observation fetch, extracted from yields_service.py (R8)
│   │   ├── riksbank_client.py       # NEW — Sweden policy-rate fetch via Riksbank REST API (R8)
│   │   ├── rates_service.py         # NEW — RateService (FEDRATE via fred.py, RIKSRATE via riksbank_client.py)
│   │   ├── index_service.py         # NEW — generalized index poller (DAX/CAC40/FTSE100/NIKKEI225; OMX can migrate onto it)
│   │   ├── yields_service.py        # CHANGED — refactored onto shared fred.py helper (no behavior change)
│   │   ├── calendar_service.py      # CHANGED — refactored onto shared fred.py helper; unchanged FRED behavior
│   │   ├── calendar_actuals.py      # CHANGED — add on_fetch_started/on_fetch_finished callbacks (R5)
│   │   ├── omx_service.py           # CHANGED — migrated onto index_service.py's generalized class, or left as-is with index_service.py added alongside (decided in tasks.md)
│   │   └── signal_strategies.py     # CHANGED — add INDICATOR_INFO table (descriptions + priority + rationale)
│   ├── reports/
│   │   ├── constants.py             # CHANGED — add PINNED_COMMODITIES, extend label table with Copper/Oil
│   │   └── reference_quote.py       # CHANGED — reuse commodity_service.py live quotes for BRENT/COPPER reference price
│   └── widgets/
│       ├── commodity_tile.py        # CHANGED — DXY label → "US Dollar Index"
│       ├── ratio_tile.py            # CHANGED — "Au/Ag" → "Gold/Silver Ratio"
│       ├── report_watchlist.py      # CHANGED — _recent_label uses METAL_LABELS instead of raw ticker
│       ├── news_panel.py            # CHANGED — meta-click spans for read-more + time_confidence marker
│       ├── news_log_screen.py       # NEW — ModalScreen browsing the news history buffer
│       ├── metal_panel.py           # CHANGED — indicator badge click regions, priority-ordered rendering
│       ├── calendar_panel.py        # CHANGED — in-flight fetch spinner per event row
│       ├── rate_tile.py             # NEW — RateTile widget (FEDRATE/RIKSRATE)
│       ├── index_tile.py            # NEW — IndexTile widget (DAX/CAC40/FTSE100/NIKKEI225)
│       ├── stock_chart_screen.py    # NEW — StockChartScreen (full chart + history strip + report/dividend sections)
│       └── daily_change_strip.py    # NEW — small widget rendering the 40-day up/down strip
│
└── quantum/
    └── app.py                       # CHANGED — wire _show_stock_chart() for quantum's own StockTile instances (Story 9 applies here too, reusing marketcore's fetch/modal)

tests/
├── marketcore/
│   ├── test_news_time.py            # CHANGED (or new) — time_confidence tagging cases
│   └── test_stock_history.py        # NEW — fetch_daily_history / fetch_dividend_info parsing
├── test_news_time.py                # CHANGED — existing goldsilver-level news timestamp test extended
├── test_ratio_tile.py               # CHANGED — updated label assertion
├── test_omx_strip.py                # CHANGED if omx_service.py migrates onto index_service.py
├── test_minicharts_settings.py      # CHANGED — new ALLOWED_MINI_TILES keys
├── test_calendar_panel.py           # CHANGED — spinner render state
├── test_calendar_actuals.py         # CHANGED — new fetch-started/finished callback assertions
├── test_report_watchlist.py         # CHANGED — recent-runs label assertion; copper/oil pinned rows
├── test_commodity_copper.py         # CHANGED if reference_quote.py's copper proxy path changes
├── test_rates_service.py            # NEW
├── test_index_service.py            # NEW
├── test_stock_chart_screen.py       # NEW — modal composition smoke test (Pilot)
└── test_dividend_info.py            # NEW
```

**Structure Decision**: No new packages, no changes to `pyproject.toml`. All new
modules land inside the existing `marketcore`/`goldsilver` package boundaries per
their existing ownership rules (symbol-agnostic reusable pieces → `marketcore`;
goldsilver-dashboard-specific composition → `goldsilver`). `quantum` gets exactly one
touch point (wiring the chart-modal trigger) since none of the other nine stories are
quantum-scoped per the spec's own framing (rate/index tiles are gold/silver dashboard
context; report/dividend info ties to goldsilver's report watchlist).

## Phasing & Sequencing (implementation strategy)

Grouped by shared plumbing so later stories can build on earlier ones; each group
keeps the test suite green before moving to the next.

1. **Shared FRED extraction** (prerequisite for Story 7, touches Story-4-adjacent
   `calendar_service.py`) — pull `fred.py` out of `yields_service.py`, re-point
   `calendar_service.py` onto it. Pure refactor, no behavior change; run existing
   `test_calendar_service_actuals.py` + real-yield tests to confirm no regression
   before adding anything new.
2. **Data-integrity fixes** (Story 1, Story 5, Story 2) — news `time_confidence` +
   history deque + news log modal; readable-name fixes (3 call sites); read-more
   click-through. These are independent of each other and of everything below;
   land first per the spec's own priority order.
3. **Indicator transparency + calendar spinner** (Story 3, Story 4) — `INDICATOR_INFO`
   table, click-region rendering in `metal_panel.py`; `ActualsFetcher` callbacks +
   spinner in `calendar_panel.py`. Both reuse the click-region contract from group 2's
   news work.
4. **Report expansion** (Story 6) — `PINNED_COMMODITIES`, label table, reference-quote
   reuse. Depends on nothing new; can run in parallel with group 3.
5. **New live tiles** (Story 7, Story 8) — `riksbank_client.py`, `rates_service.py`,
   `index_service.py`, `RateTile`, `IndexTile`, `ALLOWED_MINI_TILES` extension,
   `app.py` dispatch branches. Depends on group 1's `fred.py` extraction.
6. **Chart modal + history strip** (Story 9) — `fetch_daily_history()`,
   `_StockSpark.on_click`, `StockChartScreen` (chart + strip sections only),
   `daily_change_strip.py`. Wire into both `goldsilver/app.py` and `quantum/app.py`.
7. **Report status + dividends in the modal** (Story 10) — extends `StockChartScreen`
   from group 6 with the report/dividend sections; `report_controller.py` lookup
   helper; `fetch_dividend_info()`. Must land after group 6 since it extends the same
   screen rather than duplicating it.

> Detailed, dependency-ordered tasks are produced by `/speckit-tasks` into `tasks.md`.

## Complexity Tracking

> No constitution violations — table intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| — | — | — |
