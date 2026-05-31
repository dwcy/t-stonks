# Contract: StockService

## Module
`goldsilver.data.stock_service`

## Inputs

### Constructor
| Param                  | Type                                  | Default | Notes                                       |
|------------------------|---------------------------------------|---------|---------------------------------------------|
| `tickers`              | `list[str]`                           | —       | Raw yfinance symbols.                       |
| `handler`              | `StockHandler \| None`                | `None`  | Called with `list[StockQuote]` per refresh. |
| `stale_handler`        | `StockStaleHandler \| None`           | `None`  | Called with UTC `datetime` on full failure. |
| `refresh_interval_s`   | `float` (keyword-only)                | `60.0`  | Refresh cadence in seconds.                 |

### Public methods
```python
def start(self) -> None
async def stop(self) -> None
async def refresh_now(self) -> None
def set_tickers(self, tickers: list[str]) -> None    # live reconfiguration
```

## Outputs

### `StockQuote` per ticker
- `ticker`: str (echoes input symbol)
- `display_name`: str (= ticker, MVP — long-name lookup is a future enhancement)
- `price`: float (latest 5-min close)
- `previous_close`: float (last completed daily close)
- `intraday_closes`: `tuple[float, ...]` (today's 5-min closes, possibly empty)
- `currency`: str (`yf.Ticker.fast_info.currency` or `"USD"` fallback)
- `time`: tz-aware UTC `datetime`

### Handler invocation semantics

- `handler` is invoked **once per refresh cycle** with the full list of successful quotes.
- A ticker that fails validation or fetch is **omitted** from the list; consumers should
  detect missing tickers by diffing against the configured list.
- If the whole batch fails (every ticker None) the **stale_handler** is invoked instead;
  the regular handler is not called.

## Errors

- Constructor: raises `ValueError` if `tickers` contains non-string elements.
- `start()` while already running: no-op (matches `OmxService`).
- `stop()` is idempotent and cancels the loop task cleanly.
- `set_tickers()` updates the in-memory list for the *next* refresh — does not abort the
  in-flight refresh.

## Threading / async contract

- One asyncio task per service (`name="stock-loop"`).
- yfinance calls run inside `asyncio.to_thread` — never block the event loop.
- One thread per refresh cycle (single batch); no parallel fan-out across tickers in MVP
  (avoids yfinance rate limits).

## Failure modes

| Failure                            | Behaviour                                        |
|------------------------------------|--------------------------------------------------|
| Network unreachable                | stale_handler called; tiles keep last values    |
| yfinance returns empty DataFrame   | That ticker omitted from batch                  |
| One ticker is unknown symbol       | That ticker omitted; others still emitted       |
| Pydantic ValidationError on quote  | That ticker omitted from batch                  |
| All tickers fail                   | stale_handler invoked                            |
