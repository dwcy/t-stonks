# Data Model: Dashboard UX & Data-Quality Fixes

Phase 1 output. New/changed entities only — existing models (`Tick`, `Bar`,
`StockQuote`, `NewsItem`, `CalendarEvent`, `ReportTicker`, `ReportRun`,
`RealYieldPoint`) are referenced but only their deltas are documented here.

## NewsItem (extended)

Existing Pydantic model in `marketcore/models_macro.py`. Adds one field:

| Field | Type | Notes |
|---|---|---|
| `time_confidence` | `Literal["confirmed", "approximate"]` | **New.** `"confirmed"` only when a real `<pubDate>`/ISO date parsed successfully (R1). All fallback paths (URL-date stagger, feed-time, `now`) set `"approximate"`. |

All other fields (`source`, `title`, `url`, `published`) unchanged.

## NewsLogEntry / News Log (Story 1)

Not a new Pydantic model — a bounded `collections.deque[NewsItem](maxlen=300)` held on
the shared `_FeedService` base (`marketcore/services/news_service.py`), populated in
the existing merge/dedup step. Read-only from the UI side via a `history()` accessor.
No new persistence; lost on restart per resolved clarification (R2).

## IndicatorInfo (Story 3)

New small dataclass/model in `goldsilver/data/signal_strategies.py`, one instance per
entry in `STRATEGY_REGISTRY`:

| Field | Type | Notes |
|---|---|---|
| `key` | `str` | Matches `STRATEGY_REGISTRY` key (e.g. `"Z-Score Recoil"`). |
| `short_label` | `str` | Existing badge text (currently in `_STRATEGY_SHORT_LABELS`; this table absorbs that mapping). |
| `description` | `str` | Plain-language explanation of what the indicator measures. |
| `priority_rank` | `int` | 1 = highest priority. Fixed order: Z-Score(1), MACD(2), Bollinger(3), RSI(4), ROC(5), Slope(6). |
| `rationale` | `str` | Why this indicator ranks where it does relative to its neighbors (lag vs. noise trade-off). |

## Calendar Event Auto-Fetch State (Story 4)

Not a persisted model — ephemeral UI state. `calendar_panel.py` tracks
`_fetching_event_ids: set[str]`, driven by new `ActualsFetcher` callbacks
(`on_fetch_started`, `on_fetch_finished`). Presence in the set drives the spinner
render for that row; no data survives beyond the in-progress fetch.

## Report Ticker (extended) (Story 6)

`reports/constants.py` adds:

| Constant | Value | Notes |
|---|---|---|
| `PINNED_COMMODITIES` | `("BRENT", "COPPER")` | **New**, merged into `ReportWatchlistScreen._watchlist_entries()` alongside `PINNED_METALS`. |
| `METAL_LABELS` (renamed conceptually, same dict) | adds `"BRENT": "Oil", "COPPER": "Copper"` | Existing dict extended, not replaced — call sites (`ReportTicker.metal()`, `html_writer.py`, `_recent_label`) work unchanged since they already do a dict lookup. |

`ReportTicker.metal(symbol)` classmethod now also produces correct pinned entries for
`"BRENT"`/`"COPPER"` with no signature change.

## Policy Interest Rate (Story 7)

New model, `RatePoint` (mirrors the shape of the existing `RealYieldPoint`), in
`marketcore/models_macro.py`:

| Field | Type | Notes |
|---|---|---|
| `value` | `float` | Current rate, percent. |
| `previous` | `float \| None` | Prior observation, for change display. |
| `asof` | `date` | Effective/observation date from the source. |
| `source` | `Literal["fed", "riksbank"]` | Which of the two new services produced it — lets one tile-render function serve both. |

## Stock Exchange Index (Story 8)

New model, `IndexPoint`, in `marketcore/models_macro.py`:

| Field | Type | Notes |
|---|---|---|
| `symbol` | `str` | Internal key, e.g. `"DAX"`, `"CAC40"`, `"FTSE100"`, `"NIKKEI225"` (and `"OMX"` if migrated). |
| `level` | `float` | Current index level. |
| `previous_close` | `float` | For session change %. |
| `session_open` | `bool` | Whether the exchange is currently in its cash session (drives the "closed" indicator, FR-033). |
| `time` | `datetime` | Timestamp of this observation. |

## Daily History Strip Entry (Story 9)

New model, `DailyChange`, in `marketcore/models.py` (sits next to `Bar`):

| Field | Type | Notes |
|---|---|---|
| `date` | `date` | Trading day. |
| `close` | `float` | That day's close. |
| `change_percent` | `float` | Day-over-day % change vs. the prior entry. |
| `direction` | `Literal["up", "down", "flat"]` | Derived from `change_percent` sign (small epsilon for flat, matching `RatioTile`'s existing `flat = abs(pct) < 0.01` convention). |

Computed client-side from the same `Bar` series `fetch_daily_history()` returns — no
separate fetch or storage.

## Dividend Payment (Story 10)

New model, `DividendInfo`, in `marketcore/models_macro.py`:

| Field | Type | Notes |
|---|---|---|
| `ticker` | `str` | |
| `amount` | `float \| None` | Per-share amount of the most recent (or next known) payment. `None` when no dividend history exists. |
| `payment_date` | `date \| None` | Date of that payment. `None` alongside `amount is None`. |
| `is_forward_looking` | `bool` | `True` only if the date/amount represents a confirmed *upcoming* payment; `False` when it's the most recent historical payment shown as a fallback (R11) — the modal uses this to phrase the label correctly ("next payment" vs. "last payment") rather than imply certainty it doesn't have. |

## Relationships

```
NewsItem ──(time_confidence)──> displayed in news panel + news log
NewsLog (deque of NewsItem) ──> NewsLogScreen

STRATEGY_REGISTRY entry ──(1:1)──> IndicatorInfo ──> MetalPanel badge + description popover

CalendarEvent ──(has)──> Calendar Event Auto-Fetch State (ephemeral) ──> spinner on CalendarPanel row

ReportTicker (pinned, extended with BRENT/COPPER) ──(generates)──> ReportRun
StockChartScreen ──(looks up by ticker)──> ReportRun (from ReportController._runs)
StockChartScreen ──(membership check)──> settings.report_tickers / report_excluded

RateService (fed | riksbank) ──> RatePoint ──> RateTile (FEDRATE / RIKSRATE mini-tile)
IndexService (per exchange) ──> IndexPoint ──> IndexTile (DAX / CAC40 / FTSE100 / NIKKEI225 mini-tile)

StockTile (_StockSpark click) ──> StockChartScreen
  ├─ fetch_daily_history(ticker) ──> Bar[] ──> PriceChart.seed(...)
  ├─ Bar[] ──(derived)──> DailyChange[] (last 40) ──> history strip widget
  ├─ ReportController._runs lookup ──> latest ReportRun (if watchlisted)
  ├─ seconds_until_next_boundary(...) ──> next scheduled report time (if watchlisted)
  └─ fetch_dividend_info(ticker) ──> DividendInfo
```
