# Phase 1 — Data Model: 24-hour Sliding Chart + Stock Mini-Tiles

## New / modified Pydantic models

### `StockQuote` (new, in `goldsilver/data/models_macro.py`)

```python
class StockQuote(BaseModel):
    model_config = ConfigDict(frozen=True)

    ticker: str                          # raw yfinance symbol, e.g. "LUG.TO"
    display_name: str                    # short label for the tile (e.g. "LUG.TO")
    price: float                         # latest intraday close
    previous_close: float                # last completed daily close
    intraday_closes: tuple[float, ...]   # today's 5-min close series (sparkline data)
    currency: str                        # e.g. "CAD", "SEK", "USD"
    time: datetime                       # UTC timestamp of the latest sample

    @field_validator("price", "previous_close")
    @classmethod
    def _positive(cls, v: float) -> float:
        if v <= 0.0:
            raise ValueError(f"price must be positive: {v}")
        return v

    @field_validator("time")
    @classmethod
    def _tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("time must be timezone-aware")
        return v.astimezone(timezone.utc)

    @property
    def change(self) -> float:
        return self.price - self.previous_close

    @property
    def change_percent(self) -> float:
        if self.previous_close == 0.0:
            return 0.0
        return (self.price - self.previous_close) / self.previous_close * 100.0
```

**Notes**:
- `ticker` is the raw symbol the user typed; we render `display_name` instead of relying on
  the upstream's longName (avoids long company names in narrow tiles).
- `intraday_closes` is `tuple` (frozen). Empty tuple is legal — rendered as a flat
  sparkline placeholder.
- Currency is read from `yf.Ticker(symbol).fast_info.currency` (synchronous, cached) and
  defaults to `"USD"` if missing.

### `ChartViewState` (new, in-memory only, NOT a Pydantic model — lives in widget state)

Plain `dataclass(slots=True)` inside `widgets/chart.py`:

```python
@dataclass(slots=True)
class ChartViewState:
    zoom: Literal["24h", "3h", "1h"] = "24h"
    crosshair_index: int | None = None
    pinned_indices: set[int] = field(default_factory=set)
```

**Notes**:
- Not serialised. Per-`PriceChart` instance.
- `zoom` is mirrored to `AppSettings.chart_zoom` on user change so it persists across
  launches.
- `crosshair_index` and `pinned_indices` are pure in-session UI state.

## Modified models

### `AppSettings` (in `goldsilver/data/settings.py`)

**Add**:
```python
chart_zoom: Literal["24h", "3h", "1h"] = "24h"
chart_mode: Literal["live", "history"] = "live"
stock_tickers: list[str] = field(default_factory=_default_stock_tickers)
```

with:
```python
def _default_stock_tickers() -> list[str]:
    return ["LUG.TO", "LUG.ST", "LUMI.ST", "LUNR.V"]
```

**Keep** (was previously marked for removal):
- `timeframe_index: int = 0` — drives the **history mode** timeframe picker
  (`today / 5d / 1mo / 3mo`). Decision reversed per research.md Q4: history mode preserves
  the existing multi-day picker as a distinct mode.

**Validation**:
- `chart_zoom` invalid value → coerced to `"24h"` in `__post_init__`.
- `chart_mode` invalid value → coerced to `"live"` in `__post_init__`.
- `stock_tickers` non-list / non-str-elements → coerced to default list in `__post_init__`.
  Empty list is allowed (hides the row per FR-016).
- `timeframe_index` out of range → coerced to `0` (existing behaviour preserved).

## Service contract

### `StockService` (new, in `goldsilver/data/stock_service.py`)

```python
StockHandler = Callable[[list[StockQuote]], Awaitable[None] | None]
StockStaleHandler = Callable[[datetime], Awaitable[None] | None]

STOCK_REFRESH_INTERVAL_S = 60.0

class StockService:
    def __init__(
        self,
        tickers: list[str],
        handler: StockHandler | None = None,
        stale_handler: StockStaleHandler | None = None,
        *,
        refresh_interval_s: float = STOCK_REFRESH_INTERVAL_S,
    ) -> None: ...

    def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def refresh_now(self) -> None: ...
```

**Behaviour**:
- Refresh loop matches `OmxService` shape exactly.
- On each refresh: spawn one `asyncio.to_thread` that fetches all tickers and returns a
  list of `StockQuote` (omitting tickers that fail validation).
- `handler` is invoked once per refresh with the full list (caller diffs against current
  state to update tiles).
- `stale_handler` is invoked if the whole batch fails or all tickers return None.

## Settings file format (after migration)

```json
{
  "chart_kind": "line",
  "chart_zoom": "24h",
  "show_sma": false,
  "show_vwap": false,
  "show_day_refs": false,
  "show_news_markets": true,
  "show_news_trump": true,
  "gold_color_name": "Classic Gold",
  "silver_color_name": "Pearl",
  "metals_columns": 2,
  "stock_tickers": ["LUG.TO", "LUG.ST", "LUMI.ST", "LUNR"],
  "visible_signals": { ... },
  "signal_params": { ... },
  "marker_momentum_strategy": "",
  "marker_recoil_strategy": ""
}
```

Old `timeframe_index` is silently dropped by the existing `allowed`-field filter in
`AppSettings.load()`.

## Entity relationships

```
AppSettings (persisted)
  ├── chart_mode ────────────► PriceChart.set_mode("live" | "history")
  ├── chart_zoom ────────────► PriceChart.ChartViewState.zoom (live mode only)
  ├── timeframe_index ───────► PriceChart history-mode timeframe (history mode only)
  └── stock_tickers ─────────► StockService(tickers=...) ──► [StockQuote]
                                                              └─► StockTile (per ticker)

PriceChart (per metal)
  ├── ChartViewState (zoom, crosshair, pins)
  ├── _bars: list[Bar]  (existing — rolling 24 h trimmed on each tick)
  └── _redraw():
        compute xmin/xmax from now + zoom
        draw bars, hour ticks, half-hour scatter
        draw crosshair vline + label if active
        draw pinned dots if any

StockService (singleton)
  └── handler ── on_quotes ──► StockTileRow (Textual container, recomposes if ticker
                                            list changes)
```

## Bar history retention

The existing `PriceChart._bars` list grows unbounded. With a rolling 24 h window we must
trim periodically — otherwise after weeks the list is in the tens of thousands.

**Decision**: After each `add_point()` / `seed()`, drop bars older than 25 h from the
head (1 h buffer so the leftmost full hour tick is always available).

```python
def _trim_bars(self) -> None:
    if not self._bars:
        return
    cutoff = self._bars[-1].time - timedelta(hours=25)
    while self._bars and self._bars[0].time < cutoff:
        self._bars.pop(0)
```

## Validation summary

| Field                          | Validation                                                  | On failure                          |
|--------------------------------|-------------------------------------------------------------|-------------------------------------|
| `StockQuote.price`             | > 0                                                         | Drop quote from batch               |
| `StockQuote.previous_close`    | > 0                                                         | Drop quote from batch               |
| `StockQuote.time`              | tz-aware                                                    | Drop quote from batch               |
| `AppSettings.chart_zoom`       | in `{"24h","3h","1h"}`                                      | Coerce to `"24h"`                   |
| `AppSettings.chart_mode`       | in `{"live","history"}`                                     | Coerce to `"live"`                  |
| `AppSettings.timeframe_index`  | int in `[0, len(TIMEFRAMES))`                                | Coerce to `0`                       |
| `AppSettings.stock_tickers`    | list[str], each non-empty after strip                       | Coerce to default list              |
| `StockService` batch           | ≥1 quote returned                                           | Emit stale; tiles keep last values  |
