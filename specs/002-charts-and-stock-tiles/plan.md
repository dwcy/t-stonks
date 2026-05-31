# Implementation Plan: 24-hour Sliding Chart + Stock Mini-Tiles (+ news fixes)

**Branch**: `001-macro-economic-calendar` (working alongside the calendar spec — no new
branch cut for this feature, per current session)
**Date**: 2026-05-30
**Spec**: `specs/002-charts-and-stock-tiles/spec.md`

## Summary

Replace the metals chart's static "midnight today" origin with a **rolling 24-hour window**
that slides with wall-clock time, ticks-up zoom levels (24 h / 3 h / 1 h), and adds a
keyboard-driven crosshair with pinnable samples. The bottom axis renders two visual tiers
of ticks: tall `|` at every full hour, short `|` at every half hour (or `:15` at 1 h zoom).

In parallel, add a **stock mini-tile row** between the OMX strip and the metals panels —
up to 6 sparkline tiles per row, stretching to fill the row when fewer tickers are
configured. The list lives in `settings.json` as `stock_tickers`, defaulting to
`["LUG.TO", "LUG.ST", "LUMI.ST", "LUNR"]` (Lundin Gold on both Toronto and Stockholm,
Lundin Mining Stockholm, Intuitive Machines NASDAQ).

Three **scope additions** picked up mid-planning (folded in here for traceability):
- **EFN** added to the markets news source list (Swedish financial TV / efn.se).
- **Politico** RSS parser bug: items render as `"Latest on Politico - Politico"` /
  `"- Politico"` — caused by empty `<title>` falling through to a generic suffix; reject
  empty-after-strip titles and titles that are only the source-tag suffix.
- **Calendar compact mode** (FR-026..028): when Today has zero events, collapse the
  CalendarPanel to a single inline row that lists the next N upcoming events instead of
  rendering an empty Today column. Two-section layout returns automatically when Today
  is repopulated.

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: Textual 8.x, textual-plotext 1.x, Pydantic v2, yfinance ≥1.4,
httpx ≥0.28
**Storage**: in-memory; `settings.json` (JSON file) for persisted user preferences
**Testing**: pytest (no test infra yet on this project — see "Open Questions")
**Target Platform**: Linux + Windows Terminal (Textual cross-platform)
**Project Type**: single-process Textual TUI desktop app
**Performance Goals**: ≥1 chart redraw / 5 s without dropping ticks; crosshair keystroke
≤50 ms; stock-tile cold-start ≤15 s
**Constraints**: no backend, no DB, no API keys, no new GUI framework, no
backwards-compat hacks for old settings beyond the existing field-filter
**Scale/Scope**:
- 2 metals charts (gold, silver) with rolling 24 h windows
- 0–12 stock mini-tiles (1–2 rows of 6)
- 1 new async polling service (StockService) at 60 s cadence
- ~6 modified files, ~3 new files

## Constitution Check

*The project constitution is still a placeholder template — no concrete principles to
gate against. Falling back to the repository's CLAUDE.md and the user's global
CLAUDE.md as the de-facto constitution:*

| Rule (from CLAUDE.md)                                       | This plan complies                                                                |
|-------------------------------------------------------------|-----------------------------------------------------------------------------------|
| No comments explaining WHAT                                 | Code-change tasks will be written without explainer comments.                     |
| No dead code / commented-out blocks                         | `timeframe_index` is **removed** (not commented out).                             |
| Latest stable versions                                      | No new deps; existing pinned versions (Textual 8.x, etc.) preserved.              |
| Pydantic for boundary data                                  | `StockQuote` is a new Pydantic model with validators.                             |
| Reactive widgets, async I/O in workers                      | `StockService` follows the `OmxService` async-loop pattern.                       |
| No backend / REST / persistence layer                       | Only `settings.json` is touched; no DB, no API server.                            |
| No `.env`                                                   | Not generated.                                                                    |
| Don't add features I didn't ask for                         | Scope is exactly what the user described + the two follow-on bug/scope items.     |
| Match surrounding style                                     | New tile widget mirrors `FxTile` / `OmxStrip`; new service mirrors `OmxService`.  |

**Gate status**: ✅ pass.

## Project Structure

### Documentation (this feature)

```text
specs/002-charts-and-stock-tiles/
├── plan.md                          # this file
├── research.md                      # Phase 0 — 8 questions resolved
├── data-model.md                    # Phase 1 — StockQuote, AppSettings additions
├── quickstart.md                    # User-facing verification steps
└── contracts/
    ├── stock-service.md             # StockService contract
    └── price-chart-widget.md        # PriceChart revised contract
```

### Source code (repository root) — files touched

```text
src/goldsilver/
  app.py                             # MODIFY: wire StockService, add mode/zoom/crosshair
                                     #         keybindings, route h/z/x/PgUp/PgDn/Enter/c
  data/
    models_macro.py                  # ADD: StockQuote model
    settings.py                      # ADD: chart_zoom, chart_mode, stock_tickers;
                                     #      KEEP: timeframe_index (drives history mode)
    stock_service.py                 # NEW: StockService (mirrors OmxService)
    news_service.py                  # DONE: placeholder filter tightened; EFN added
  widgets/
    __init__.py                      # ADD: StockTile, StockRow exports
    chart.py                         # MODIFY: set_mode (live/history), rolling 24h,
                                     #         zoom, crosshair, pins, half-hour scatter
                                     #         ticks, _trim_bars
    stock_tile.py                    # NEW: StockTile widget (sparkline + label)
    stock_row.py                     # NEW: StockRow container (Grid layout 1×6)
    plot_settings.py                 # MODIFY: keep timeframe radio (history-mode),
                                     #         add zoom radio (live-mode), add mode toggle
    calendar_panel.py                # MODIFY: compact single-row view when Today empty
                                     #         (FR-026..028)
    news_panel.py                    # DONE: EFN source style added
  styles/
    app.tcss                         # MODIFY: add #stock-row, .stock-tile rules,
                                     #         CalendarPanel.-compact one-row variant
```

**Structure Decision**: Existing single-project layout under `src/goldsilver/`. The
spec-tree above is appended in place — no module reshuffles. Two new widgets co-locate
with their peers (`fx_tile.py` neighbours `stock_tile.py`).

## Implementation phases (not executed by /speckit-plan — for /speckit-tasks)

1. **Settings migration** — add `chart_zoom`, `chart_mode`, `stock_tickers`. **Keep**
   `timeframe_index`, `TIMEFRAMES` and the `_timeframe_*` properties in `app.py` — they
   now drive history mode (research.md Q4 decision: keep history mode).
2. **StockService + StockQuote** — new model, new async service mirroring `OmxService`.
3. **StockTile + StockRow** — new widgets; wire into `compose()` in `app.py`.
4. **Chart engine rework** — `set_mode()`, rolling 24 h (live), `_trim_bars()`,
   `set_zoom()`, half-hour scatter ticks. History mode reuses the existing show-all-bars
   path. Keep existing line / candle / SMA / VWAP / day-refs / marker code working in
   both modes at every zoom level.
5. **Crosshair + pins (live mode only)** — `activate_crosshair`, `move_crosshair`,
   `pin_current`, key bindings in `app.py`, mouse-wheel-zoom override on the chart
   widget. Suppress these bindings while `chart_mode == "history"`.
6. **PlotSettings UI update** — keep the timeframe radio (history-mode control), add a
   zoom radio (live-mode control), add a mode toggle (live ↔ history), surface
   `stock_tickers` editing note.
7. **News fixes (scope add)** — ✅ shipped in this planning pass:
   - 7a. `news_service._is_placeholder()` extended to reject empty-after-lstrip titles,
         `Latest on X - X` / `Breaking on X - X` / `News from X - X` patterns, and
         titles that are only the source-tag suffix.
   - 7b. EFN added to `NewsSource` Literal and `NEWS_FEEDS` at `https://www.efn.se/rss`
         (the `/feed/` URL 404s; `/rss` returns valid RSS 2.0 with 2000+ items).
8. **Calendar compact mode (scope add)** — `widgets/calendar_panel.py`: detect
   empty-Today snapshot, swap the two-`VerticalScroll` layout for a single `Static` row
   that renders `Text` like
   `"No events today · next: <weekday HH:MM SRC title> · …"`. Truncate to panel width
   with ellipsis. Restore two-section layout when Today repopulates (reactive on
   `snapshot`).
9. **Visual QA** — `uv run goldsilver`, verify SC-001..SC-009 manually plus the new
   FR-026..028 compact-mode transitions (try with a real empty-Today calendar response
   and a populated one).

*(Phase 2 task generation is the job of `/speckit-tasks` — this file stops at the planning
boundary.)*

## Open questions / NEEDS CLARIFICATION

1. **Lundin Royalties ticker** — RESOLVED (2026-05-30, user confirmed `LUNR.V`, TSX
   Venture, CAD). Default `stock_tickers` is now
   `["LUG.TO", "LUG.ST", "LUMI.ST", "LUNR.V"]`. Verified queryable via yfinance.
2. **EFN feed URL** (scope add). `https://www.efn.se/feed/` is the assumed source —
   verify it returns parseable RSS during implementation; if not, scrape the homepage
   article list or drop EFN with a note.
3. **Chart history beyond 24 h** — RESOLVED (2026-05-30, user confirmed): keep multi-day
   `today / 5d / 1mo / 3mo` view as a separate **history mode** (FR-024, FR-025). Mode
   toggle bound to `h`; `timeframe_index` retained; new `chart_mode` field added. See
   research.md Q4 for design details.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| Two render tiers (large + small ticks) on a single plotext canvas | User explicitly asked for two tick sizes; plotext only supports one xticks layer | Forking plotext would be far more work; the scatter-marker hack is contained inside `_redraw()` |

## Cross-references

- Spec: `spec.md` (FR-001 .. FR-024, SC-001 .. SC-009)
- Research: `research.md` (Q1 .. Q8)
- Data model: `data-model.md`
- Contracts: `contracts/stock-service.md`, `contracts/price-chart-widget.md`
- Quickstart: `quickstart.md`
