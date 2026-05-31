---
description: "Task list for 24-hour Sliding Chart + Stock Mini-Tiles (+ history mode + calendar compact + news fixes)"
---

# Tasks: 24-hour Sliding Chart + Stock Mini-Tiles

**Input**: Design documents from `/specs/002-charts-and-stock-tiles/`
**Prerequisites**: `plan.md`, `spec.md` (5 user stories), `research.md`, `data-model.md`,
`contracts/stock-service.md`, `contracts/price-chart-widget.md`

**Tests**: NOT requested. The project currently has no test infra; tasks below are
production-code only. Manual verification follows `quickstart.md`.

**Organization**: Tasks are grouped by user story so each P1 / P2 increment is
independently deliverable. Two non-user-story scope blocks (history-mode +
calendar-compact + already-shipped news fixes) sit as their own phases.

## Path conventions

Single project. All source under `src/goldsilver/`. Spec docs under
`specs/002-charts-and-stock-tiles/`.

---

## Phase 1: Setup (shipped already — kept for traceability)

**Purpose**: Track scope items completed during the planning pass.

- [x] T001 Tighten `_is_placeholder` in `src/goldsilver/data/news_service.py` to reject Politico-style empty / suffix-only / "Latest on X" titles
- [x] T002 Add `EFN` source via `https://www.efn.se/rss` in `src/goldsilver/data/news_service.py` (`NEWS_FEEDS` tuple)
- [x] T003 Add `EFN` to `NewsSource` Literal in `src/goldsilver/data/models_macro.py`
- [x] T004 Add `EFN` style entry to `_SOURCE_STYLE` in `src/goldsilver/widgets/news_panel.py`

---

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: Models, settings, and helpers every downstream story depends on.

**⚠️ CRITICAL**: No user-story work begins until this phase is complete.

- [x] T005 [P] Add `StockQuote` Pydantic model (ticker, display_name, price, previous_close, intraday_closes, currency, time + `change` / `change_percent` properties + validators) in `src/goldsilver/data/models_macro.py`
- [x] T006 [P] Extend `AppSettings` in `src/goldsilver/data/settings.py`: add `chart_zoom: Literal["24h","3h","1h"] = "24h"`, `chart_mode: Literal["live","history"] = "live"`, `stock_tickers: list[str]` with `_default_stock_tickers()` returning `["LUG.TO","LUG.ST","LUMI.ST","LUNR.V"]`; **keep** `timeframe_index` (now drives history mode); add coercion in `__post_init__`
- [x] T007 [P] Add `_trim_bars(self)` helper to `PriceChart` in `src/goldsilver/widgets/chart.py` — drop bars older than `(bars[-1].time - 25h)` from the head; call from `seed()` and `add_point()`
- [x] T008 [P] Add `ChartViewState` `@dataclass(slots=True)` (`zoom`, `crosshair_index`, `pinned_indices`) at module top of `src/goldsilver/widgets/chart.py`; replace ad-hoc state fields once US1/US2/US3 land

**Checkpoint**: Foundation ready — user-story work may now proceed in parallel.

---

## Phase 3: User Story 1 — Rolling 24-hour gold/silver chart (Priority: P1) 🎯 MVP

**Goal**: Replace the "today-from-midnight" chart origin with a rolling 24-hour window
anchored to the live tick on the right edge. Hour ticks (large `|`) and half-hour ticks
(smaller `|`) along the bottom axis.

**Independent Test**: Launch the TUI mid-afternoon. Within 5 s the gold chart fills the
panel with ~24 h of bars; rightmost x-tick label is the current local hour, leftmost is
(now − 24 h). Leave running 10 min; right edge advances, old samples scroll off the left.

- [x] T009 [US1] Rewrite `PriceChart._redraw()` x-axis window logic in `src/goldsilver/widgets/chart.py`: compute `right_edge = (bars[-1].time - origin) / 60s`, `window_minutes = {"24h":1440,"3h":180,"1h":60}[self._zoom]`, call `self.plt.xlim(right_edge - window_minutes, right_edge)`
- [x] T010 [US1] Rewrite `_compute_ticks()` in `src/goldsilver/widgets/chart.py` to emit **hour ticks only** (large `|`) inside the current visible window; label each tick `"%H"` (or `"%H:%M"` when window ≤ 1 h)
- [x] T011 [US1] Add `_render_halfhour_marks()` in `src/goldsilver/widgets/chart.py`: scatter-plot `marker="|"` at `y = self.plt.ylim()[0]` for every `:30` offset (24 h / 3 h zoom) inside the visible window; dim grey color
- [x] T012 [US1] Remove the `x_origin = stockholm_midnight_utc()` path from `_seed_panel()` in `src/goldsilver/app.py`; always seed with rolling 24 h derived from `MetalsService.fetch_history(period="2d", interval="1m")` filtered to `now - 24h .. now`
- [x] T013 [US1] Wire `_trim_bars()` into `add_point()` in `src/goldsilver/widgets/chart.py` so the buffer never exceeds 25 h of bars during long runs
- [x] T014 [US1] Update `_compute_ticks()` callers in `src/goldsilver/widgets/chart.py` to use the new rolling window — make sure `apply_features` / `apply_session_refs` / `add_marker` still render correctly

**Checkpoint**: Gold and silver charts show a live, rolling 24 h window with hour +
half-hour bottom-axis ticks. Default zoom unchanged from 24 h. MVP shippable.

---

## Phase 4: User Story 2 — Zoom to 3 h / 1 h (Priority: P1)

**Goal**: Add 24 h / 3 h / 1 h zoom levels reachable from keyboard and mouse wheel.

**Independent Test**: Press `z`; chart shrinks to last 3 h with live edge on right. Press
again; last 1 h with 15-min half-ticks and hour mark at the hour boundary. Mouse-wheel
inside the chart area cycles zoom (on terminals that support it).

- [x] T015 [P] [US2] Add `set_zoom(zoom)` and `cycle_zoom()` methods on `PriceChart` in `src/goldsilver/widgets/chart.py`; update `ChartViewState.zoom` and call `_redraw()`
- [x] T016 [US2] Adjust `_render_halfhour_marks()` in `src/goldsilver/widgets/chart.py` to emit ticks at `:15 / :30 / :45` offsets when `self._zoom == "1h"` instead of `:30` only
- [x] T017 [US2] Add `Binding("z", "cycle_zoom", "Zoom")` to `GoldSilverApp.BINDINGS` and `action_cycle_zoom()` in `src/goldsilver/app.py` that calls `chart.cycle_zoom()` on every `MetalPanel`'s chart
- [x] T018 [US2] Implement `on_mouse_scroll_up` / `on_mouse_scroll_down` in `PriceChart` in `src/goldsilver/widgets/chart.py` — wheel-up zooms in, wheel-down zooms out
- [x] T019 [US2] Replace the timeframe radio with a zoom radio (`24h / 3h / 1h`) in `src/goldsilver/widgets/plot_settings.py`; wire it to `AppSettings.chart_zoom`
- [x] T020 [US2] Persist `chart_zoom` from the in-memory mirror into `AppSettings` on every change in `_on_settings_change()` in `src/goldsilver/app.py`; restore on startup
- [x] T021 [US2] Smoke-test SC-003 (`set_zoom` round-trip ≤200 ms) by eye while live ticks are flowing — note any regressions

**Checkpoint**: Live mode is feature-complete (rolling 24 h + zoom). MVP++ shippable.

---

## Phase 5: User Story 4 — Stock mini-tile row (Priority: P1)

**Goal**: Render a horizontal row of up to 6 stock mini-tiles between the OMX strip and
the metals grid. Each tile: ticker label, price, day %, 4-row sparkline. No SMA / VWAP /
markers — clean sparkline only.

**Independent Test**: Launch with default config. Within 15 s, 4 equal-width tiles render
in one row (`LUG.TO`, `LUG.ST`, `LUMI.ST`, `LUNR.V`), each with ticker, price, % change,
sparkline. Each pair of Lundin Gold tiles shows similar % moves (same company, different
currencies).

- [x] T022 [P] [US4] Implement `StockService` in `src/goldsilver/data/stock_service.py` per `contracts/stock-service.md` — 60 s loop, `asyncio.to_thread` batch via `yf.Ticker(sym).history(period="2d", interval="5m")`, emit `list[StockQuote]` via handler, `stale_handler` on total failure
- [x] T023 [P] [US4] Implement `StockTile(Static)` widget in `src/goldsilver/widgets/stock_tile.py` — `reactive[StockQuote | None]`, renders a 4-row block: line 1 = ticker + price + change %, lines 2-4 = sparkline via embedded `PlotextPlot` (no axes, no SMA, no markers); mirror visual conventions of `FxTile`
- [x] T024 [P] [US4] Implement `StockRow(Grid)` container in `src/goldsilver/widgets/stock_row.py` — accepts `list[str]` tickers, composes one `StockTile` per ticker, grid-size `min(len(tickers), 6) × ceil(len(tickers)/6)`; hide widget entirely when ticker list is empty
- [x] T025 [US4] Export `StockTile` and `StockRow` from `src/goldsilver/widgets/__init__.py`
- [x] T026 [US4] Wire `StockService` and `StockRow` into `GoldSilverApp.__init__` and `compose()` in `src/goldsilver/app.py` — place row right after `OmxStrip`, before the `#metals` `Grid`; add `_on_stock_quotes(list[StockQuote])` and `_on_stock_stale(datetime)` handlers
- [x] T027 [US4] Add `#stock-row { layout: horizontal; height: 4; padding: 0 2; }` and `.stock-tile { width: 1fr; height: 4; }` rules to `src/goldsilver/styles/app.tcss`
- [x] T028 [US4] Start / stop the `StockService` from `on_mount` / `on_unmount` and add it to `action_refresh()` in `src/goldsilver/app.py`
- [x] T029 [US4] Verify sparkline does not pull in `_SOURCE_STYLE` / SMA / VWAP / markers code — keep `StockTile._redraw()` strictly close-only

**Checkpoint**: Stock row renders with the four default Lundin tickers. Sparklines tick
once per minute. Live edge of metals charts still advances.

---

## Phase 6: User Story 5 — Configure stocks via settings.json (Priority: P1)

**Goal**: Editing `stock_tickers` in `settings.json` and restarting the TUI swaps the
mini-tile row contents accordingly.

**Independent Test**: Edit `%APPDATA%\goldsilver\settings.json` `stock_tickers` to e.g.
`["LUG.TO", "AAPL"]`. Restart. Two tiles render at 1/2 width each.

- [x] T030 [US5] Read `self._settings.stock_tickers` and pass to `StockService` and `StockRow` constructors in `src/goldsilver/app.py`
- [x] T031 [US5] Hide the `StockRow` (skip yield in `compose()`) when `self._settings.stock_tickers` is empty in `src/goldsilver/app.py`
- [x] T032 [US5] Handle invalid tickers gracefully — drop from batch in `StockService` (already covered by T022), and have `StockTile` render `--` placeholder when its `reactive[StockQuote]` stays `None` longer than 30 s in `src/goldsilver/widgets/stock_tile.py`
- [ ] T033 [US5] (Optional, low-risk) Add a "stock tickers" hint paragraph to the `PlotSettingsScreen` body in `src/goldsilver/widgets/plot_settings.py` pointing the user at `settings.json` for live edits
- [x] T034 [US5] Walk through `specs/002-charts-and-stock-tiles/quickstart.md` "Edit your stock tickers" steps to verify SC-008

**Checkpoint**: Default + custom ticker lists both work without code edits.

---

## Phase 7: User Story 3 — Crosshair + pins (Priority: P2)

**Goal**: Add a movable crosshair on the metals chart with an HH:MM + price readout and
the ability to pin samples that persist after crosshair dismissal.

**Independent Test**: Press `x` — vertical guide line appears at the rightmost sample,
`border_subtitle` shows `HH:MM  price`. Press `←` a few times; line moves left, subtitle
updates. Press `Enter`; gold dot pinned. Press `x` again to dismiss; pin remains. Press
`c` to clear pins.

- [x] T035 [P] [US3] Add `activate_crosshair()`, `dismiss_crosshair()`, `move_crosshair(step: int)`, `pin_current()`, `clear_pins()` methods on `PriceChart` in `src/goldsilver/widgets/chart.py`; update `ChartViewState` fields; trigger `_redraw()` on every state change
- [x] T036 [US3] In `PriceChart._redraw()` in `src/goldsilver/widgets/chart.py`, when `view_state.crosshair_index is not None`, draw `self.plt.vline(xs[idx], color=(180,180,220))` and set `self.border_subtitle = f"{bars[idx].time.astimezone():%H:%M}  {bars[idx].close:.2f}"`
- [x] T037 [US3] In `PriceChart._redraw()` in `src/goldsilver/widgets/chart.py`, render pinned dots: for each `idx in view_state.pinned_indices` inside visible x-range, `self.plt.scatter([xs[idx]], [closes[idx]], marker="●", color=(255,213,107))`
- [x] T038 [US3] Add bindings `x`, `left`, `right`, `pageup`, `pagedown`, `enter`, `c` to `GoldSilverApp.BINDINGS` in `src/goldsilver/app.py`; route each to the active chart (suggested: route to whichever `MetalPanel`'s chart was focused last, or to both)
- [x] T039 [US3] Suppress the `left` / `right` / `enter` bindings while crosshair is **not** active in `src/goldsilver/app.py` (prevent surprise behaviour when no crosshair is on)
- [x] T040 [US3] Verify SC-005 (≤50 ms per `move_crosshair` keystroke) by eye while live ticks are flowing

**Checkpoint**: Live mode + crosshair + pins all coexist; live edge keeps advancing during
crosshair use.

---

## Phase 8: Chart mode toggle — live ↔ history (FR-024 / FR-025)

**Purpose**: Keep the existing `today / 5d / 1mo / 3mo` timeframe picker available as a
distinct **history mode**, toggled with `h`. No user-story label — this is a cross-cutting
scope-add the user confirmed.

- [x] T041 [P] Add `_mode: Literal["live","history"]` field, `set_mode(mode)`, `cycle_mode()` methods on `PriceChart` in `src/goldsilver/widgets/chart.py`
- [x] T042 In `PriceChart._redraw()` in `src/goldsilver/widgets/chart.py`, branch on `self._mode`: live → rolling 24 h `xlim` (from US1); history → `xlim(0, right_edge_minutes)` showing all seeded bars
- [x] T043 Add `Binding("h", "cycle_chart_mode", "Mode")` and `action_cycle_chart_mode()` in `src/goldsilver/app.py`; call `chart.cycle_mode()` on each metal chart, then re-seed via `_seed_all()` (history mode uses `MetalsService.fetch_history(period=TIMEFRAMES[timeframe_index][1], interval=TIMEFRAMES[timeframe_index][2])`)
- [x] T044 In `_seed_panel()` in `src/goldsilver/app.py`, branch on `self._chart_mode`: live → rolling 24 h seed (US1, T012); history → existing multi-day seed using `timeframe_index`
- [x] T045 In `src/goldsilver/app.py`, **disable live-mode live-tick application** (`add_point`, marker drawing) while `_chart_mode == "history"` — `_on_tick` should still update price stats / signals / FX-style data but not call `panel.chart.add_point()`
- [x] T046 In `src/goldsilver/widgets/plot_settings.py`, add a `RadioSet` for mode (`Live` / `History`); keep the existing timeframe radio but **disable** it when mode is `Live`; reveal the zoom radio (T019) only when mode is `Live`
- [x] T047 Persist `chart_mode` via `_on_settings_change()` in `src/goldsilver/app.py`; restore on startup; reseed if mode differs from session start
- [x] T048 Make `cycle_zoom`, `activate_crosshair`, `move_crosshair`, `pin_current`, `clear_pins`, and the mouse-wheel handler no-ops when `_mode == "history"` in `src/goldsilver/widgets/chart.py`

**Checkpoint**: `h` toggles live ↔ history. Live mode keeps all of US1/US2/US3 behaviour;
history mode reverts to the pre-feature `today / 5d / 1mo / 3mo` picker with no rolling
window and no crosshair.

---

## Phase 9: Calendar compact mode (FR-026..028, scope-add)

**Purpose**: When the macro calendar's Today section is empty, collapse the
`CalendarPanel` into a single inline row showing the next N upcoming events.

- [x] T049 In `CalendarPanel` in `src/goldsilver/widgets/calendar_panel.py`, add `_is_today_empty(snapshot)` helper that returns `True` when no `CalendarDay` with `bucket == "today"` carries any events
- [x] T050 Refactor `compose()` in `src/goldsilver/widgets/calendar_panel.py` to lazily mount either the existing two-`VerticalScroll` layout or a single `Static` (`id="cal-compact"`) depending on the snapshot; switch via `remove_children()` + remount in `_refresh_body()` when the empty-Today state flips
- [x] T051 In `_refresh_body()` in `src/goldsilver/widgets/calendar_panel.py`, when compact, render the next 3 upcoming events inline: `"No events today · next: Wed 14:30 FED CPI · Thu 13:45 ECB rate · Fri 08:00 RIKSBANK minutes"`, truncate trailing event with `…` if width is exceeded
- [x] T052 Add `.calendar-compact { height: 1; padding: 0 2; content-align: left middle; color: #7a7a8a; }` rule to `src/goldsilver/styles/app.tcss`; keep existing `CalendarPanel` rules for the two-section layout
- [x] T053 Add reactive transition test by walking through the midnight-rollover acceptance scenario from FR-028 manually (mock a snapshot with no Today, then one with Today re-populated — see if the layout swaps without restart)

**Checkpoint**: Calendar panel is one row tall on empty-Today days; flips back to the
full two-section layout when events appear under Today.

---

## Phase 10: Polish & cross-cutting

- [x] T054 [P] Run `uv run goldsilver` and walk through `specs/002-charts-and-stock-tiles/quickstart.md` end-to-end; capture any visual regressions
- [x] T055 [P] Verify success criteria SC-001..SC-009 from `spec.md`; document any that don't pass and what remediation is needed
- [x] T056 Confirm no orphan code remains — search for now-unreachable `stockholm_midnight_utc` calls, removed `TIMEFRAMES` references that should have been gated by mode (they should NOT have been removed — confirm they remain wired for history mode)
- [x] T057 Run `uv tree` and verify no new dependency was inadvertently added; `pyproject.toml` should be unchanged from the start of this feature
- [x] T058 Make sure `compose()` order in `src/goldsilver/app.py` reads top-to-bottom: Header → macro-strip → OMX strip → StockRow → metals Grid → CalendarPanel → NewsPanel → status-bar → Footer
- [x] T059 Update the `Footer` binding labels by inspecting `Binding(...)` calls in `src/goldsilver/app.py` so the footer reflects the new keys (`h`, `z`, `x`, `c`)

---

## Dependencies & Execution Order

### Phase dependencies

- **Phase 1 (Setup — news fixes)**: ✅ already shipped — no blocking work.
- **Phase 2 (Foundational)**: blocks Phases 3–9. T005–T008 are independent of each other and may run in parallel.
- **Phase 3 (US1 — rolling 24 h)**: blocks Phase 4 (zoom builds on the rolling-window engine) and Phase 8 (history mode shares the redraw branching).
- **Phase 4 (US2 — zoom)**: depends on Phase 3.
- **Phase 5 (US4 — stock row)**: independent of Phases 3/4 — can run in parallel with US1/US2.
- **Phase 6 (US5 — stock config)**: depends on Phase 5.
- **Phase 7 (US3 — crosshair)**: depends on Phase 3 (needs rolling window in place to interpret crosshair `x` positions).
- **Phase 8 (mode toggle)**: depends on Phases 3, 4, 7 — needs everything that gets gated off in history mode to exist first.
- **Phase 9 (calendar compact)**: independent of all chart / stock work — can run in parallel.
- **Phase 10 (Polish)**: depends on everything above.

### User-story dependencies

| Story | Depends on            | Can run in parallel with |
|-------|-----------------------|--------------------------|
| US1   | Phase 2               | US4, Phase 9             |
| US2   | US1                   | US4, US5, Phase 9        |
| US3   | US1                   | US4, US5, Phase 9        |
| US4   | Phase 2               | US1, US2, US3, Phase 9   |
| US5   | US4                   | US1, US2, US3, Phase 9   |

### Within each story

- Foundational models / settings before any service or widget that consumes them.
- Service before container widget before app wiring.
- App wiring before keybinding additions.

### Parallel opportunities

- Phase 2: T005 (model), T006 (settings), T007 (trim helper), T008 (state dataclass) — 4 parallel.
- Phase 5: T022 (service), T023 (tile), T024 (row) — 3 parallel.
- Phase 8: T041 (mode methods) parallel with planning of T042; rest sequential.
- Phase 10: T054 + T055 + T057 in parallel.

---

## Parallel example: kicking off after Foundational checkpoint

```bash
# After Phase 2 (T005..T008) completes, three streams can fan out:

# Stream A — Live-mode chart engine (US1 → US2 → US3 → Phase 8)
Task: "T009 Rewrite PriceChart._redraw() x-axis window logic"
Task: "T010 Hour-tick rendering"
Task: "T011 Half-hour scatter marks"
Task: "T012 Replace seed origin in app.py"

# Stream B — Stock tile row (US4 → US5)
Task: "T022 StockService"
Task: "T023 StockTile widget"
Task: "T024 StockRow container"

# Stream C — Calendar compact mode (Phase 9)
Task: "T049 _is_today_empty helper"
Task: "T050 Conditional compose() layout"
Task: "T051 Compact inline rendering"
Task: "T052 .calendar-compact CSS rule"
```

---

## Implementation strategy

### MVP first (US1 only)

1. ✅ Phase 1 (news fixes already shipped).
2. Phase 2: Foundational (T005..T008).
3. Phase 3: US1 — rolling 24-hour chart (T009..T014).
4. **STOP and VALIDATE**: gold and silver chart panels show a continuously sliding 24 h
   window with hour + half-hour bottom ticks. This is the single most valuable change in
   the feature.

### Incremental delivery

1. MVP (US1) → demo.
2. + US2 (zoom) → demo.
3. + US4 (stock row) and US5 (config) → demo (high-value addition for a Lundin-portfolio
   user).
4. + US3 (crosshair) → demo.
5. + Phase 8 (history mode toggle) → demo (restores the multi-day chart the user kept).
6. + Phase 9 (calendar compact) → demo.
7. Phase 10: Polish.

### Solo-developer strategy

Working alone, the dependency chain US1 → US2 → US3 → Phase 8 is the longest path. Drop
US4/US5 in parallel between US1 and US2 to keep momentum if the stock-fetch work blocks
on yfinance rate-limit issues.

---

## Notes

- `[P]` tasks touch different files and have no dependencies on incomplete tasks.
- `[Story]` labels (`[US1]`..`[US5]`) map back to the spec's user stories. Phases 1, 2,
  8, 9, 10 have no `[Story]` label by design.
- News fixes are checked off as shipped (Phase 1) — they're tracked here for audit only.
- All file paths are project-relative under `src/goldsilver/` or
  `specs/002-charts-and-stock-tiles/`.
- Run `uv run goldsilver` at every checkpoint — Textual catches most regressions on
  visual inspection.
- The constitution file at `.specify/memory/constitution.md` is still a placeholder; the
  de-facto gates are CLAUDE.md rules (plan.md: Constitution Check section).
