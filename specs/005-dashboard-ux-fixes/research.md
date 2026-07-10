# Research: Dashboard UX & Data-Quality Fixes

Phase 0 output. Each item resolves one area of the spec against the actual codebase
(explored directly — file/line citations point at the pre-change state).

## R1 — News timestamp integrity (Story 1, FR-001..003)

- **Decision**: Add a `time_confidence: Literal["confirmed", "approximate"]` field to
  `NewsItem` (`marketcore/models_macro.py`). Keep the existing 3-tier fallback chain in
  `marketcore/services/news_service.py::_parse_rss` (`_parse_pub_date` →
  `_date_from_url` + stagger → `now`), but only the first tier sets `confirmed`; the
  URL-date-stagger and `now` fallbacks set `approximate`. Rendering marks approximate
  items with a small "~" prefix instead of a plain timestamp.
- **Rationale**: The bug isn't the fallback chain itself (PressTV genuinely omits
  `<pubDate>` on many items, so *some* fallback is unavoidable) — it's that the
  fallback result is displayed with the same confidence as a real timestamp. Minimal,
  targeted change: keep computing a display timestamp, just stop asserting it's exact.
- **Alternatives considered**: Drop items with no real pubDate (rejected — spec FR-001
  wants them shown, just honestly labeled); block rendering until a "real" time is
  resolved (adds latency for no benefit, most feeds simply never populate it).

## R2 — News log (Story 1, FR-004/005)

- **Decision**: Add a bounded `collections.deque(maxlen=300)` history buffer to the
  shared `_FeedService` base in `marketcore/services/news_service.py`, populated in the
  same merge step that already builds the per-refresh `merged` list (dedup by link is
  already implemented there — reuse it for the log too). Expose via a
  `history() -> tuple[NewsItem, ...]` method. New `NewsLogScreen(ModalScreen)` (new
  file, `goldsilver/widgets/news_log_screen.py`) renders it as a scrollable list,
  reachable via a new key binding / button from the news panel.
- **Rationale**: Confirmed clarification — rolling in-session buffer, no restart
  persistence required. A `deque` needs no new dependency and bounds memory
  automatically; reusing the existing dedup logic avoids a second merge implementation.
- **Alternatives considered**: SQLite/file-backed log (rejected by clarification —
  scope explicitly capped to in-session).

## R3 — Read more click-through (Story 2, FR-006..008)

- **Decision**: `NewsItem.url` already exists and is populated
  (`marketcore/models_macro.py:174`) but unused for interaction. Instead of
  restructuring `news_panel.py`'s single concatenated `Text` render into per-item
  widgets, attach `meta={"news_url": item.url}` to each item's title span (the same
  technique `goldsilver/widgets/calendar_panel.py::_CalendarBody.on_click` already uses
  via `style.meta.get("cal_event")`), then add an `on_click` handler on the panel that
  reads `event.style.meta.get("news_url")` and calls `webbrowser.open(url)` when
  present.
- **Rationale**: Smallest diff that reuses an established in-repo pattern; avoids a
  rewrite to `ListView`/`ListItem` that would also require re-doing the panel's compact
  multi-column layout.
- **Alternatives considered**: `ListView` per item (rejected — bigger diff, no
  behavioral advantage over meta-click spans for a read-only "open link" action).

## R4 — Indicator descriptions + priority (Story 3, FR-009..013)

- **Decision**: Add an `INDICATOR_INFO: dict[str, IndicatorInfo]` table next to
  `STRATEGY_REGISTRY` in `goldsilver/data/signal_strategies.py` (content lives with the
  strategy definitions it describes, not the UI layer). Priority order (highest first):
  Z-Score, MACD, Bollinger Bands, RSI, ROC, Slope — ranked by signal
  confirmation-window length (slow/confirmed → fast/noisy), per the resolved spec
  clarification. `metal_panel.py::_render_indicators()` gets a `meta={"indicator": key}`
  span per badge (same click-region technique as R3/R4), a new
  `_expanded_indicator: reactive[str | None]` toggled on click, and reorders iteration
  to follow the fixed priority list instead of `STRATEGY_REGISTRY`/`visible_signals`
  dict order.
- **Rationale**: Matches the in-repo click-region convention already used for calendar
  events; keeps indicator metadata colocated with the strategies it documents so the
  two can't drift independently.
- **Alternatives considered**: A Textual `Tooltip` widget (rejected — zero precedent in
  this codebase; meta-click matches the existing "click to see detail" language already
  used for calendar events).

## R5 — Macro calendar auto-fetch spinner (Story 4, FR-014..016)

- **Decision**: No new fetch-triggering logic — `calendar_actuals.py::due_events()`
  already fires the per-event fetch once the grace period passes. Add
  `on_fetch_started(event_id)` / `on_fetch_finished(event_id, ok)` callbacks from
  `ActualsFetcher` to `calendar_panel.py`, which tracks an in-flight `set[str]` and
  reuses the `_SPINNER_FRAMES` / `set_interval(0.12, ...)` pattern already implemented
  in `goldsilver/widgets/report_watchlist.py` to animate that event row while its id is
  in the set.
- **Rationale**: The fetch-in-progress state already exists implicitly in
  `ActualsFetcher._dispatched`; this only needs a UI-facing signal, and a working
  spinner implementation already exists in-repo to copy rather than reinvent.

## R6 — Readable naming (Story 5, FR-017..019)

- **Decision**:
  - `commodity_tile.py`: `DXY` label value → `"US Dollar Index"`.
  - `ratio_tile.py`: literal `"Au/Ag "` (confirmed at line 47) → `"Gold/Silver Ratio "`.
  - `report_watchlist.py::_recent_label` (lines 259-268, confirmed it renders raw
    `run.ticker`) → use `METAL_LABELS.get(run.ticker, run.label)` so the "recent
    reports" rows read "Gold"/"Silver" like the ticker rows above them already do
    (`_build_ticker_rows` already shows `"Gold (XAU)"` — only the recent-runs list was
    leaking the bare ticker).
- **Rationale**: Confirmed via direct code read that the ticker rows were *already*
  correct; only the recent-runs list and the two mini-tile labels needed the change —
  narrows this story to 3 call sites, not a repo-wide sweep.

## R7 — Copper & oil reports (Story 6, FR-020..023)

- **Decision**: Add `PINNED_COMMODITIES = ("BRENT", "COPPER")` alongside the existing
  `PINNED_METALS` in `reports/constants.py`, merged into
  `ReportWatchlistScreen._watchlist_entries()`. Extend the label table with
  `"BRENT": "Oil", "COPPER": "Copper"`. For the reference-quote proxy
  (`reports/reference_quote.py::_METAL_PROXY`), reuse `commodity_service.py`'s
  already-fetched live quotes (Avanza for COPPER, yfinance `BZ=F` for BRENT) directly
  as ground truth, rather than adding a second yfinance-proxy path like gold/silver
  needed.
- **Rationale**: Gold/silver needed a yfinance proxy (`GC=F`/`SI=F`) specifically
  *because* Avanza doesn't offer them as spot instruments. Copper and oil don't have
  that problem — `commodity_service.py` already fetches live data for both — so
  reusing it is simpler than replicating the metals' workaround where the underlying
  reason for it doesn't apply.
- **Alternatives considered**: Add `HG=F`/`CL=F` yfinance proxies mirroring the metals
  path exactly (rejected — redundant with data already fetched elsewhere in the app).

## R8 — USA & Sweden interest rates (Story 7, FR-024..027)

- **Decision**: Extract a small `goldsilver/data/fred.py` helper
  (`fetch_observation(series_id, api_key) -> RateObservation | None`) from the
  `parse_observations()` logic duplicated today in `yields_service.py` — both it and
  `calendar_service.py` independently define `FRED_KEY_ENV`/base URL and hand-roll the
  `httpx.AsyncClient.get(...)` call. New `RateService` (mirrors `RealYieldService`'s
  shape/lifecycle) polls FRED series `DFF` (Federal Funds Effective Rate, daily) for
  USA using the existing `GOLDSILVER_FRED_KEY` env var. For Sweden, FRED has no
  equivalent policy-rate series — Sweden's Riksbank publishes its own free public REST
  API (`developer.api.riksbank.se`, no mandatory key for low request volume); add
  `goldsilver/data/riksbank_client.py` as a second, distinct client. Both refresh on
  the same 4-hour cadence as `REAL_YIELD_REFRESH_S` (policy rates change at scheduled
  meetings, not intraday). New tile registered as `FEDRATE` / `RIKSRATE` mini-tile
  keys.
- **Rationale**: `DFF` is a confirmed, real FRED series requiring only the
  already-configured key — no new credential to manage. Sweden has no reliable FRED
  proxy for the actual policy rate (only interbank/money-market series exist there),
  so its own official API is the only accurate direct source — consistent with this
  app's existing principle (documented in `CLAUDE.md`) of not collapsing a hybrid feed
  into a single approximate source just for convenience.
- **Alternatives considered**: Scrape the Riksbank rates web page (rejected — fragile,
  no contract); use a Sweden money-market/interbank FRED series as a proxy (rejected —
  spec explicitly wants the actual policy rate).

## R9 — International stock exchanges (Story 8, FR-028..034)

- **Decision**: Generalize `omx_service.py`'s single-symbol pattern into a small
  parameterized index service (constructor takes `display_name`, `yf_symbol`, session
  timezone) instead of copy-pasting it 4 more times. Covers the new DAX (`^GDAXI`),
  CAC 40 (`^FCHI`), FTSE 100 (`^FTSE`), Nikkei 225 (`^N225`) — OMX (`^OMX`) can migrate
  onto the same class opportunistically. Session open/closed detection reuses
  `marketcore/session.py`'s existing tz-parameterized helpers, parameterized per
  exchange (Europe/Berlin, Europe/Paris, Europe/London, Asia/Tokyo) against each
  market's standard cash-session hours. New/extended tile widget follows
  `CommodityTile`'s existing single-line render shape. 4 new `ALLOWED_MINI_TILES`
  keys.
- **Rationale**: yfinance already supports `^`-prefixed index tickers (proven by the
  existing OMX integration) — no new dependency. One parameterized service instead of
  five near-identical ones follows this repo's existing size-discipline convention
  (e.g. `PollingService` was already extracted for the same reason during feature 004).
- **Alternatives considered**: Five independent copy-pasted services (rejected — fails
  the "duplicate on 3rd copy" DRY rule already applied elsewhere in this codebase).

## R10 — Chart detail modal (Story 9, FR-035..039)

- **Decision**: `PriceChart` (`marketcore/widgets/chart.py`) is confirmed to be a
  "dumb" widget — it takes bars via `seed()`/`add_point()`/`apply_session_refs()` and
  has no internal knowledge of `history_store.py`'s file-based persistence (that's
  metal-specific, wired externally in `goldsilver/app.py`). So Story 9 needs zero
  changes to `chart.py` itself — only new plumbing around it:
  - New `on_click` on `_StockSpark` (`marketcore/widgets/stock_tile.py`, confirmed to
    have no existing click handler and no conflict with `PlotextPlot`'s base
    behavior), forwarding to a new app method `_show_stock_chart(ticker)` mirroring the
    existing `_show_calendar_event(event)` push-screen pattern.
  - New `fetch_daily_history(ticker, period="3mo", interval="1d")` in
    `marketcore/services/stock_service.py`, converting the yfinance result into `Bar`
    models (3 months comfortably covers 40 trading days including holidays).
  - New `StockChartScreen(ModalScreen)` (new file, mirrors
    `CalendarEventScreen`/`AlertsScreen`'s push/dismiss lifecycle) embeds a `PriceChart`
    fed via `seed()`, plus a new small strip widget rendering the last 40
    `DailyHistoryStripEntry` values (up/down arrow + day-over-day %) computed from the
    same fetched series — no second fetch needed.
- **Rationale**: Because `PriceChart` was already built data-source-agnostic (confirmed
  by tracing its 3 public feed methods), this story is additive plumbing rather than a
  chart rewrite — lowest-risk path.
- **Alternatives considered**: Extend `history_store.py`'s day-JSON persistence to
  arbitrary stock tickers (rejected for this feature — that mechanism is metal-specific
  and disk-backed; a direct per-open yfinance fetch matches how stock tile data is
  already fetched fresh rather than persisted).

## R11 — Report status & dividends in the modal (Story 10, FR-040..045)

- **Decision**: `StockChartScreen` (R10) additionally receives the app's
  already-maintained recent-runs cache — confirmed to live as
  `ReportController._runs: list[ReportRun]`, capped at 50 and deduplicated per ticker,
  reloaded from on-disk sidecars at startup via `load_recent_runs(out_root())` (so it
  already survives restarts). The modal looks up
  `next((r for r in runs if r.ticker == ticker), None)` for the "latest report" link,
  and checks `ticker in settings.report_tickers and ticker not in settings.report_excluded`
  to decide whether to show the report section at all (FR-042). "Next scheduled report
  time" is computed on demand by calling the existing free function
  `seconds_until_next_boundary(stockholm_now(), interval_minutes)` from
  `reports/scheduler.py` — confirmed `ReportScheduler` has no stored "next run" state
  today, but the function needed to compute it already exists and needs no scheduler
  changes. New `fetch_dividend_info(ticker)` in `stock_service.py` uses
  `yf.Ticker(ticker).dividends` (confirmed nothing dividend-related exists in the repo
  today); since yfinance doesn't reliably expose a forward "next ex-dividend date" for
  every ticker, "next known dividend" falls back to the most recent historical payment
  with the modal clearly stating when only historical (not forward-looking) data is
  available, satisfying FR-045's "no misleading blank field" requirement.
- **Rationale**: Reuses two data sources that already exist in memory
  (`ReportController._runs`) or as an easily-callable pure function
  (`seconds_until_next_boundary`) rather than inventing new persistence or scheduler
  state. Dividend fetch follows the same `yf.Ticker(...)` access pattern
  `stock_service.py` already uses for price history.
- **Alternatives considered**: A paid dividend-calendar data provider (rejected — out
  of scope/cost; yfinance's historical series plus an honest fallback state is
  sufficient per FR-045).

## Cross-cutting notes

- No new third-party dependencies are required anywhere above — `httpx`, `yfinance`,
  and `textual`/`textual-plotext` already cover every new data source (FRED, Riksbank
  REST, yfinance indices/dividends/history).
- New service modules (`fred.py`, `riksbank_client.py`, a generalized index service,
  `rates_service.py`, dividend fetch in `stock_service.py`) keep each file under the
  Python module LoC soft cap (200) per `rules/python.md` — none of these are large
  enough to approach it individually.
- `StockChartScreen` is a new Textual screen; budgeted against the 250 soft-cap /
  400 hard-cap for Textual views. If the chart + strip + report/dividend sections
  push it over the soft cap, the worker/render split pattern (view owns `compose()`,
  a sibling module owns data-fetch orchestration) applies — call this out explicitly
  in tasks.md if it happens.
