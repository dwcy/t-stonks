# Contract: Stock Chart Detail Modal

Governs Story 9 (full chart on mini-chart click) and Story 10 (report status +
dividends inside the same modal).

## Trigger

`_StockSpark.on_click` (new — `marketcore/widgets/stock_tile.py`) posts a message
carrying the tile's ticker. The owning app (`goldsilver/app.py` for goldsilver stock
tiles, `quantum/app.py` for quantum tiles — both already import `StockTile` from
`marketcore`) handles it via a new `_show_stock_chart(ticker: str)` method that
constructs and pushes `StockChartScreen`, mirroring the existing
`_show_calendar_event(event)` → `CalendarEventScreen` pattern exactly (same
push/dismiss lifecycle, same `BINDINGS = [("escape", "dismiss", "Close")]` convention).

## `StockChartScreen(ModalScreen[None])` — inputs

```python
StockChartScreen(
    ticker: str,
    bars: Sequence[Bar],                     # from fetch_daily_history(ticker)
    recent_report: ReportRun | None,          # None if not on the report watchlist
    next_report_at: datetime | None,          # None if not on the report watchlist
    dividend: DividendInfo | None,            # None if no dividend data at all
)
```

The caller (app-level `_show_stock_chart`) is responsible for assembling these four
pieces before construction — the screen itself does no fetching, matching
`CalendarEventScreen`'s existing convention of receiving fully-resolved data.

## Composition contract

1. **Chart section** — embeds a `PriceChart` instance, fed via
   `chart.seed(bars, kind="line", show_sma=True)` — the same public method
   `MetalPanel.seed_history()` already calls. No changes to `PriceChart` itself.
2. **History strip** — a new small widget (e.g. `DailyChangeStrip`) rendering up to 40
   `DailyChange` entries (derived from `bars`, not separately fetched) as a wrapped row
   of `▲+1.2%` / `▼-0.8%` tokens colored via the existing `UP_COLOR`/`DOWN_COLOR`
   palette in `widgets/format.py`. Fewer than 40 available bars renders fewer entries
   (FR-038) — never blocks composing the screen.
3. **Report section** — rendered only when `recent_report is not None or next_report_at is not None`
   (FR-042: omitted entirely for non-watchlisted tickers). Shows the next scheduled
   run time (formatted from `next_report_at`) and, if `recent_report` exists, a
   clickable label opening `recent_report.html_path` (reuse the `webbrowser.open()`
   helper introduced for Story 2/R3).
4. **Dividend section** — always rendered. When `dividend is None` or
   `dividend.amount is None`, shows a fixed "No dividend information available"
   state (FR-045) instead of blank fields. When `dividend.is_forward_looking` is
   `False`, the label reads "Last payment" rather than "Next payment" to avoid
   implying certainty the data doesn't have.

## Dismiss contract

`escape` or a close button calls `self.dismiss()`. No callback result is required
(`ModalScreen[None]`) — the live dashboard tiles underneath are untouched by
construction/dismissal (FR-039), since `StockTile`'s own refresh loop is independent
of any modal state.

## Data-fetch functions this contract depends on (new, in `marketcore/services/stock_service.py`)

```python
async def fetch_daily_history(ticker: str, *, period: str = "3mo") -> list[Bar]: ...
async def fetch_dividend_info(ticker: str) -> DividendInfo: ...
```

Both are plain async functions (not services with a start/stop lifecycle) — invoked
once per modal open, not polled, since neither daily history nor dividend data needs
live refresh inside a short-lived modal view.
