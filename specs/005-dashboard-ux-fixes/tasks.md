---

description: "Task list for Dashboard UX & Data-Quality Fixes"
---

# Tasks: Dashboard UX & Data-Quality Fixes

**Input**: Design documents from `specs/005-dashboard-ux-fixes/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included, matching this repo's existing per-feature test convention
(`tests/test_*.py` per widget/service — see `test_news_time.py`, `test_ratio_tile.py`,
`test_omx_strip.py`, etc.). Not strict TDD write-first — tests land alongside/after
their implementation task within each story, consistent with how existing tests were
added to this codebase.

**Organization**: Ten user stories (P1–P10, matching spec.md's Story 1–10 numbering
1:1). Each is independently implementable and testable per spec.md's own framing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1–US10, matching spec.md Story 1–10
- File paths are exact, from plan.md's Project Structure

## Path Conventions

Existing multi-package monorepo — `src/marketcore/`, `src/goldsilver/`, `src/quantum/`,
`tests/` (flat for goldsilver-scoped tests, `tests/marketcore/`, `tests/quantum/`
subdirs for those packages). No new packages.

---

## Phase 1: Setup

**Purpose**: Baseline check before touching anything (no new deps, no scaffolding
needed per plan.md's Technical Context).

- [ ] T001 Run `uv sync` and the existing suite (`uv run pytest`) to confirm a green
      baseline on `005-dashboard-ux-fixes` before making changes

---

## Phase 2: Foundational

**Purpose**: Cross-story blocking prerequisites.

**Note**: research.md and plan.md confirm none of the ten stories share a hard
blocking prerequisite — each adds net-new, story-scoped models/services/widgets. The
one shared refactor (extracting `fred.py` out of `yields_service.py`) only serves
Story 7 and is scoped as that story's first task, not a global blocker. **No tasks in
this phase** — proceed directly to the user story phases below, in priority order or
in parallel.

---

## Phase 3: User Story 1 - Trustworthy news timestamps and a news log (Priority: P1) 🎯 MVP

**Goal**: Every news item's displayed time honestly reflects confirmed vs. approximate
data, and a browsable log retains items beyond the live panel's visible window.

**Independent Test**: Fresh app start shows no fabricated "just now" timestamps;
scrolled-off headlines remain visible via the news log.

- [X] T002 [P] [US1] Add `time_confidence: Literal["confirmed", "approximate"]` field
      to `NewsItem` in `src/marketcore/models_macro.py`
- [X] T003 [US1] Update the 3-tier fallback in `_parse_rss`/`_parse_pub_date`
      (`src/marketcore/services/news_service.py`) so only a real parsed `<pubDate>`
      sets `time_confidence="confirmed"`; URL-date-stagger and `now` fallbacks set
      `"approximate"` (depends on T002)
- [X] T004 [P] [US1] Add a bounded `collections.deque(maxlen=300)` history buffer to
      `_FeedService` in `src/marketcore/services/news_service.py`, populated in the
      existing merge/dedup step; expose via `history() -> tuple[NewsItem, ...]`
- [X] T005 [US1] Render a `~` marker for `time_confidence == "approximate"` items in
      `src/goldsilver/widgets/news_panel.py` (depends on T002)
- [X] T006 [P] [US1] Create `NewsLogScreen(ModalScreen[None])` in
      `src/goldsilver/widgets/news_log_screen.py`, listing `NewsService.history()`
      newest-first, `escape` to dismiss (depends on T004)
- [X] T007 [US1] Wire a news-log open action/binding in `src/goldsilver/app.py`
      pushing `NewsLogScreen` (depends on T006)
- [X] T008 [P] [US1] Extend `tests/test_news_time.py` with cases for confirmed vs.
      approximate tagging and the 300-item deque cap

**Checkpoint**: News timestamps are honest and history is browsable — independently
shippable.

---

## Phase 4: User Story 2 - Jump straight to the full article (Priority: P2)

**Goal**: A "read more" click on any news item with a link opens the source article.

**Independent Test**: Click "read more" on any item with a link; confirm the browser
opens the correct article.

- [X] T009 [US2] Attach `meta={"news_url": item.url}` to each item's title span (only
      when `item.url` is truthy) in `src/goldsilver/widgets/news_panel.py`'s render
      function, per `contracts/click-region-interactions.md`
- [X] T010 [US2] Add `on_click` handler to the news panel reading
      `event.style.meta.get("news_url")` and calling `webbrowser.open(url)` when
      present, in `src/goldsilver/widgets/news_panel.py` (depends on T009)
- [X] T011 [P] [US2] Add a test asserting no "read more" affordance is emitted for
      items with a missing/malformed URL, in `tests/test_news_time.py` or a new
      `tests/test_news_panel_click.py`

**Checkpoint**: Read-more works independently of Story 1's log/marker changes.

---

## Phase 5: User Story 3 - Understand what each signal indicator means and why it matters (Priority: P3)

**Goal**: Clicking an indicator badge reveals a description; badges display in a
fixed priority order with stated rationale.

**Independent Test**: Click each of the six badges; confirm description + rationale
appears in Z-Score → MACD → BB → RSI → ROC → Slope order.

- [X] T012 [US3] Add `IndicatorInfo` dataclass + `INDICATOR_INFO: dict[str, IndicatorInfo]`
      table (description, `priority_rank`, rationale per data-model.md); absorb the
      existing `_STRATEGY_SHORT_LABELS` mapping into it. Implemented in a new sibling
      module `src/goldsilver/data/signal_strategy_info.py` rather than inside
      `signal_strategies.py` — that file already carries a >400 LoC justification
      comment, and this descriptive content is a separable concern from the strategy
      computation classes.
- [X] T013 [US3] Attach `meta={"indicator": key}` to each badge span and reorder
      `_render_indicators()` to iterate by `priority_rank` in
      `src/goldsilver/widgets/metal_panel.py` (depends on T012)
- [X] T014 [US3] Add `expanded_indicator: reactive[str | None]` + `on_click` toggle
      (expand/collapse, no effect on live values) + description rendering beneath the
      badge row in `src/goldsilver/widgets/metal_panel.py` (depends on T013). Named
      without a leading underscore (unlike the plan's `_expanded_indicator`) to match
      every other reactive field's naming convention in this file and sidestep any
      ambiguity in Textual's `watch_<name>` resolution for underscore-prefixed
      reactives.
- [X] T015 [P] [US3] Add a test asserting priority order and toggle behavior in
      `tests/test_metal_panel_indicators.py` (new), plus
      `tests/test_signal_strategy_info.py` for INDICATOR_INFO data integrity.

**Checkpoint**: Indicator transparency ships independently.

---

## Phase 6: User Story 4 - See when the macro calendar is auto-refreshing (Priority: P4)

**Goal**: A spinner shows on a calendar event's row while its actual-figure fetch is
in flight.

**Independent Test**: Wait for an event's scheduled time to pass by ~1 minute;
confirm a spinner appears until the actual value (or "unavailable") resolves.

- [X] T016 [US4] Add `on_fetch_started(key)` / `on_fetch_finished(key, ok)` callback
      hooks to `CalendarService` in `src/goldsilver/data/calendar_service.py`
      (`_fetch_and_notify`, wrapping the existing `_check_due()`-triggered
      `fetcher.fetch(...)` calls), keyed by the existing
      `calendar_actuals_store.event_key(event) -> str` rather than inventing a new
      key type
- [X] T017 [US4] Track `_fetching: set[str]` in
      `src/goldsilver/widgets/calendar_panel.py` via new `apply_fetch_started`/
      `apply_fetch_finished` methods, wired from `app.py` (depends on T016)
- [X] T018 [US4] Reuse the `_SPINNER_FRAMES` / `set_interval(0.12, ...)` pattern from
      `src/goldsilver/widgets/report_watchlist.py` to animate a row's spinner when
      `event_key(event)` is in `_fetching`, in
      `src/goldsilver/widgets/calendar_panel.py` (depends on T017)
- [X] T019 [P] [US4] Extend `tests/test_calendar_panel.py` and
      `tests/test_calendar_service_actuals.py` with spinner-state and
      callback-firing assertions

**Checkpoint**: Calendar auto-fetch feedback ships independently.

---

## Phase 7: User Story 5 - Read symbols and report titles as plain names (Priority: P5)

**Goal**: "Au"/"DXY" and report-ticker shorthand are replaced with readable names
everywhere they're user-facing.

**Independent Test**: Ratio and DXY tiles show readable names; report screen's ticker
rows and recent-reports list both read "Gold"/"Silver".

- [X] T020 [P] [US5] Change the DXY label to `"Dollar Index"` in
      `src/goldsilver/widgets/commodity_tile.py` and `src/goldsilver/widgets/plot_settings.py`
      (mini-tile settings picker also showed "DXY (USD index)")
- [X] T021 [P] [US5] Change `"Au/Ag "` to `"Gold/Silver Ratio "` in
      `src/goldsilver/widgets/ratio_tile.py`, plus the "Au cheap"/"Ag cheap" extreme-zone
      hints to "Gold cheap"/"Silver cheap" (SC-007 requires zero "Au" instances) and the
      settings picker's "Au/Ag ratio" label in `plot_settings.py`
- [X] T022 [P] [US5] Fix `_recent_label` in `src/goldsilver/widgets/report_watchlist.py`
      to use `METAL_LABELS.get(run.ticker, run.ticker)` instead of the raw `run.ticker`
- [X] T023 [P] [US5] Update `tests/test_ratio_tile.py` and `tests/test_report_watchlist.py`
      assertions for the new label strings

**Checkpoint**: Readable naming ships independently — pure text/label changes, no
new logic.

---

## Phase 8: User Story 6 - Generate reports for copper and oil (Priority: P6)

**Goal**: Copper and oil are pinned, generatable report tickers using the full
existing analysis pipeline.

**Independent Test**: Generate a Copper report and an Oil report from the report
screen; confirm both appear pinned alongside Gold/Silver and produce a report in the
same style/location.

- [X] T024 [US6] Add `PINNED_COMMODITIES = ("BRENT", "COPPER")` and extend the label
      table with `"BRENT": "Oil", "COPPER": "Copper"` in
      `src/goldsilver/reports/constants.py`. Also extended `TickerKind` to
      `Literal["metal", "commodity", "stock"]` and added `ReportTicker.commodity()`/
      `pinned_commodity_tickers()` in `reports/models.py`, and wired
      `pinned_commodity_tickers()` into `ReportService.full_watchlist()` — the plan
      didn't call these out explicitly but they're required for `run_all()` to
      actually generate the two new pinned tickers.
- [X] T025 [US6] Merge `PINNED_COMMODITIES` into
      `ReportWatchlistScreen._watchlist_entries()` in
      `src/goldsilver/widgets/report_watchlist.py` (depends on T024)
- [X] T026 [US6] Reuse `commodity_service.py`'s live BRENT/COPPER quotes as the
      reference-quote source (instead of adding new yfinance proxies) in
      `src/goldsilver/reports/reference_quote.py` (depends on T024). Extracted
      `fetch_commodity_quote()` as a standalone function out of
      `CommodityService._fetch`/`_fetch_copper_avanza` so both the live poller and
      the one-shot report reference-quote lookup share the same fetch code.
      `verdict_tracker.py`'s post-hoc backtest still uses a yfinance HG=F/BZ=F proxy
      (unaffected by this — that's a different, direction-only accuracy check, not
      the live reference quote).
- [X] T027 [P] [US6] Extend `tests/test_report_watchlist.py`,
      `tests/test_commodity_copper.py`, and `tests/test_report_service_watchlist.py`
      to cover the two new pinned tickers; added `tests/test_reference_quote.py` for
      the new commodity fetch/format path.

**Checkpoint**: Copper/oil reports ship independently.

---

## Phase 9: User Story 7 - Track USA and Sweden policy interest rates (Priority: P7)

**Goal**: Live FEDRATE and RIKSRATE mini-tiles show the current US and Swedish
central bank policy rates.

**Independent Test**: Add `FEDRATE`/`RIKSRATE` to mini-tiles; confirm both show a
current rate value, refreshed on a slow (4h) cadence.

- [X] T028 [US7] Extract shared FRED fetch/parse into new `src/goldsilver/data/fred.py`
      (`fred_api_key()`, `parse_fred_pair()`, `fetch_fred_pair()`), reusing the
      observation-parsing logic previously duplicated for real-yield
- [X] T029 [US7] Re-point `src/goldsilver/data/yields_service.py` onto `fred.py`
      (kept its public `parse_observations()` wrapper for backward compat with
      `tests/test_yields_service.py`; no behavior change) (depends on T028)
- [X] T030 [P] [US7] Re-point `src/goldsilver/data/calendar_service.py`'s FRED
      release-dates call onto the shared `fred_api_key()` lookup (no behavior
      change; the `/fred/releases/dates` endpoint itself is unrelated to
      `fetch_fred_pair`, so only the key lookup is shared) (depends on T028)
- [X] T031 [P] [US7] Add `RatePoint` model + `RateSource` to
      `src/marketcore/models_macro.py` (`value`, `previous`, `asof`,
      `source: Literal["fed", "riksbank"]`); re-exported via the
      `goldsilver/data/models_macro.py` facade
- [X] T032 [P] [US7] Create `src/goldsilver/data/riksbank_client.py` fetching Sweden's
      policy rate from `api.riksbank.se/swea/v1` (live-verified against the real
      API during implementation — series `SECBREPOEFF`, no key required, current
      rate 1.75%; "previous" is the last *distinct* value over a 400-day lookback,
      not just the prior calendar day, since the series repeats the flat value
      daily between meetings)
- [X] T033 [US7] Create `src/goldsilver/data/rates_service.py` (`RateService`,
      mirrors `RealYieldService`'s start/stop/refresh_now shape) — FEDRATE via
      `fred.py` + series `DFF`, RIKSRATE via `riksbank_client.py`; 4h refresh cadence
      (depends on T028, T031, T032)
- [X] T034 [US7] Create `src/goldsilver/widgets/rate_tile.py` (`RateTile`, reactive
      `RatePoint`, single-line render matching `RealYieldTile`'s shape, missing-key
      hint for the fed source only) (depends on T031)
- [X] T035 [US7] Add `FEDRATE`/`RIKSRATE` to `ALLOWED_MINI_TILES` in
      `src/goldsilver/data/settings.py` and the mini-tile settings picker label map
      in `plot_settings.py`; wire `_RATE_SOURCE_BY_ID` dispatch + service
      start/stop/refresh_now lifecycle in `src/goldsilver/app.py`, per
      `contracts/mini-tile-registry.md` (depends on T033, T034)
- [X] T036 [P] [US7] Add `tests/test_fred.py`, `tests/test_riksbank_client.py`,
      `tests/test_rates_service.py`, `tests/test_rate_tile.py`; extended
      `tests/test_minicharts_settings.py` for the two new keys

**Checkpoint**: Interest rate tiles ship independently (after the `fred.py`
extraction, which only this story needs).

---

## Phase 10: User Story 8 - Track German, French, British, and Japanese stock exchanges (Priority: P8)

**Goal**: DAX, CAC 40, FTSE 100, and Nikkei 225 mini-tiles show live level + session
change + open/closed state.

**Independent Test**: Add the four index keys to mini-tiles; confirm each shows a
level, change, and a "closed" indicator outside trading hours.

- [X] T037 [P] [US8] Add `IndexPoint`/`IndexSymbol` model to
      `src/marketcore/models_macro.py` (`symbol`, `level`, `previous_close`,
      `session_open`, `time`), re-exported via the goldsilver facade
- [X] T038 [US8] Create `src/goldsilver/data/index_service.py` — a parameterized
      index poller (`IndexDefinition(yf_symbol, tz, open_time, close_time)`) covering
      DAX (`^GDAXI`), CAC 40 (`^FCHI`), FTSE 100 (`^FTSE`), Nikkei 225 (`^N225`);
      session open/closed via a local weekday+time-window check per exchange tz
      (depends on T037). Also extracted `src/goldsilver/data/yf_daily.py`
      (`fetch_daily_close_pair`) shared between this and `commodity_service.py`'s
      yfinance path, since both needed the identical "last two daily closes" fetch —
      not called out in the plan but a direct DRY consequence of writing this file.
- [X] T039 [US8] Create `src/goldsilver/widgets/index_tile.py` (`IndexTile`, reactive
      `IndexPoint`, renders a "closed" marker when `session_open is False`) (depends
      on T037)
- [X] T040 [US8] Add `DAX`/`CAC40`/`FTSE100`/`NIKKEI225` to `ALLOWED_MINI_TILES` in
      `src/goldsilver/data/settings.py` and the mini-tile settings picker label map;
      wire the `_INDEX_IDS` dispatch branch + per-exchange service
      start/stop/refresh_now lifecycle in `src/goldsilver/app.py`, per
      `contracts/mini-tile-registry.md` (depends on T038, T039)
- [X] T041 [US8] **Deviation from plan, deliberate**: did NOT migrate
      `omx_service.py`'s `^OMX` poller onto `index_service.py`. On inspection, OMX's
      fetch already computes a 25-day history + YTD change feeding `OmxStrip`'s
      dedicated weekly-calendar widget (4 weeks of daily up/down symbols) — a
      materially richer data need than the new tiles' single current-level +
      previous-close. `IndexPoint`/`IndexService` were scoped to match the new
      tiles' actual (simpler) requirement per `CommodityTile`'s pattern; forcing OMX
      onto that shape would have either lost its weekly-calendar data or bent
      `IndexService` back into something as complex as `OmxService`, defeating the
      simplification. `omx_service.py`/`omx_strip.py`/`tests/test_omx_strip.py` are
      unchanged.
- [X] T042 [P] [US8] Add `tests/test_index_service.py` (session open/closed per
      exchange timezone + refresh/stale paths) and `tests/test_index_tile.py`;
      extended `tests/test_minicharts_settings.py` for the four new keys

**Checkpoint**: International index tiles ship independently.

---

## Phase 11: User Story 9 - Open a full detail chart from a tile's mini chart (Priority: P9)

**Goal**: Clicking a stock tile's mini sparkline opens a modal with a full detail
chart and a 40-day up/down history strip.

**Independent Test**: Click a stock tile's mini chart; confirm the modal opens with a
chart + strip, and closes back to an unaffected live dashboard.

- [ ] T043 [P] [US9] Add `DailyChange` model to `src/marketcore/models.py` (`date`,
      `close`, `change_percent`, `direction`)
- [ ] T044 [US9] Add `fetch_daily_history(ticker, period="3mo")` to
      `src/marketcore/services/stock_service.py`, converting `yf.Ticker(...).history()`
      into `Bar` models (depends on nothing new — reuses existing `Bar`)
- [ ] T045 [US9] Add `on_click` to `_StockSpark` in
      `src/marketcore/widgets/stock_tile.py`, posting a message carrying the tile's
      ticker (confirmed no conflicting click handler exists)
- [ ] T046 [US9] Create `src/goldsilver/widgets/daily_change_strip.py` — small widget
      rendering up to 40 `DailyChange` entries as `▲+1.2%`/`▼-0.8%` tokens using
      `widgets/format.py`'s existing `UP_COLOR`/`DOWN_COLOR` palette (depends on
      T043)
- [ ] T047 [US9] Create `src/goldsilver/widgets/stock_chart_screen.py` —
      `StockChartScreen(ModalScreen[None])` per `contracts/chart-detail-modal.md`,
      composing a `PriceChart` (fed via `.seed(bars, ...)`) + the history strip
      (chart/strip sections only — report/dividend sections added in US10) (depends
      on T043, T046)
- [ ] T048 [US9] Add `_show_stock_chart(ticker)` to `src/goldsilver/app.py`, calling
      `fetch_daily_history()` and pushing `StockChartScreen`, mirroring the existing
      `_show_calendar_event` pattern (depends on T044, T045, T047)
- [ ] T049 [P] [US9] Add the same `_show_stock_chart(ticker)` wiring to
      `src/quantum/app.py` for its own `StockTile` instances (depends on T044, T045,
      T047)
- [ ] T050 [P] [US9] Add `tests/marketcore/test_stock_history.py` for
      `fetch_daily_history()` parsing and `DailyChange` derivation; add
      `tests/test_stock_chart_screen.py` (Pilot-based mount/render smoke test) for
      the modal's chart + strip sections

**Checkpoint**: Chart detail modal ships independently across both apps.

---

## Phase 12: User Story 10 - See report status and dividends in the chart detail modal (Priority: P10)

**Goal**: The chart detail modal additionally shows report-watchlist status (next
scheduled run + latest report link) and dividend info for the viewed stock.

**Independent Test**: Add a stock to the report watchlist, open its chart modal;
confirm next-run time, latest-report link, and dividend info (or a clear "no
dividend" state) all appear; confirm a non-watchlisted stock's modal has no report
section.

- [ ] T051 [P] [US10] Add `DividendInfo` model to `src/marketcore/models_macro.py`
      (`ticker`, `amount`, `payment_date`, `is_forward_looking`)
- [ ] T052 [US10] Add `fetch_dividend_info(ticker)` to
      `src/marketcore/services/stock_service.py` using `yf.Ticker(ticker).dividends`,
      falling back to the most recent historical payment with
      `is_forward_looking=False` when no forward data exists (depends on T051)
- [ ] T053 [US10] Add a by-ticker lookup helper over `self._runs` to
      `src/goldsilver/report_controller.py` (`latest_run_for(ticker) -> ReportRun | None`)
- [ ] T054 [US10] Extend `StockChartScreen` (`src/goldsilver/widgets/stock_chart_screen.py`)
      with the report section (next-run time via `seconds_until_next_boundary()` from
      `reports/scheduler.py`, latest-report link via T053; omitted entirely when the
      ticker isn't on the report watchlist per FR-042) and the dividend section
      (always rendered; "No dividend information available" when `dividend.amount is
      None`; "Last payment" vs. "Next payment" label per `is_forward_looking`)
      (depends on T052, T053)
- [ ] T055 [US10] Update `_show_stock_chart(ticker)` in `src/goldsilver/app.py` to
      pass `recent_report`, `next_report_at`, and `dividend` into `StockChartScreen`
      per `contracts/chart-detail-modal.md` (depends on T053, T054)
- [ ] T056 [P] [US10] Add `tests/test_dividend_info.py` for `fetch_dividend_info()`
      parsing/fallback; extend `tests/test_stock_chart_screen.py` with report-section
      presence/absence and dividend-state assertions

**Checkpoint**: All ten stories now independently functional.

---

## Phase 13: Polish & Cross-Cutting Concerns

- [ ] T057 [P] Run the full `quickstart.md` manual verification pass across both apps
- [ ] T058 [P] Confirm each new/changed file stays within the LoC budgets in
      `rules/python.md` (`StockChartScreen` is the one flagged as worth checking in
      research.md's cross-cutting notes — split into a sibling data-orchestration
      module if it exceeds the 250 soft cap)
- [ ] T059 Run the full suite (`uv run pytest`) and fix any regressions across all
      ten stories together
- [ ] T060 [P] Update `CLAUDE.md` if any new env var, module, or data source needs
      documenting beyond what `quickstart.md` already covers

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Empty — no cross-story blockers (see note above)
- **User Stories (Phase 3–12)**: Each depends only on Setup; stories are otherwise
  mutually independent and may proceed in parallel or in priority order (P1→P10)
- **Polish (Phase 13)**: Depends on whichever stories are in scope for a given release

### User Story Dependencies

All ten stories are independent of each other per spec.md's design. The only
intra-story sequencing is:
- **US9 → US10**: US10 extends `StockChartScreen`, created in US9 — must land after
  it (T054 depends on T047).
- **US7's `fred.py` extraction (T028)** only serves US7 itself, not other stories.

### Parallel Opportunities

- All `[P]`-marked tasks within a story touch different files and can run
  concurrently once that story's non-`[P]` groundwork tasks land
- Different user stories can be staffed in parallel by different agents/developers —
  the only real cross-story file overlap is `src/goldsilver/app.py` (touched by US1,
  US4 optionally, US7, US8, US9), so coordinate that file's edits if running stories
  concurrently, or serialize just the `app.py` wiring tasks (T007, T035, T040, T048)

---

## Parallel Example: User Story 7

```bash
# After T028 (fred.py extraction) lands, these can run together:
Task: "Add RatePoint model in src/marketcore/models_macro.py"                 # T031
Task: "Create riksbank_client.py in src/goldsilver/data/riksbank_client.py"   # T032

# Then, once T031+T032 are done:
Task: "Create rates_service.py"     # T033
Task: "Create rate_tile.py"          # T034 (only needs T031, can start alongside T033)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Skip Phase 2 (empty)
3. Complete Phase 3: User Story 1 (news timestamp integrity + log)
4. **STOP and VALIDATE**: Run `quickstart.md` step 1 independently
5. Ship — this alone fixes the most actively-misleading bug in the spec

### Incremental Delivery

Ship in spec priority order (P1→P10), validating each story's quickstart.md step
before moving to the next. Stories 9→10 must land in that order; everything else can
be reordered freely to match available time/priority.

### Parallel Team Strategy

With multiple developers: one owns US1/US2/US5 (news + naming, all touch
`news_panel.py`/`report_watchlist.py`), one owns US3/US4 (indicator + calendar, share
the click-region contract), one owns US7/US8 (new live tiles, share the mini-tile
registry contract and the `fred.py` extraction), one owns US9→US10 sequentially (the
one real intra-story dependency), one owns US6 solo (fully independent). Coordinate
`app.py` wiring tasks across owners since it's the one shared file.
