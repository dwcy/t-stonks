# gold-and-silver — Real-time TUI for Gold & Silver Prices

A personal terminal dashboard that streams live gold and silver prices with
sparkline-style charts. Cross-platform (Linux-primary, Windows Terminal supported).

## Stack

- **Language:** Python 3.12+
- **TUI framework:** [Textual](https://textual.textualize.io/)
- **Charts:** [textual-plotext](https://github.com/Textualize/textual-plotext) (plotext widget for Textual)
- **Market data (hybrid — two upstream feeds):**
  - **Live spot price:** `goldprice.org` (`/dbXRates/USD`), polled every 5s (`httpx` async). Near real-time (~10s upstream cadence). Drives the ticking `price` field only.
  - **Reference close + day H/L:** Avanza's public `GOLDSP` / `SILVERSP` index endpoints (`/_api/market-guide/stock/{orderbookId}`), refreshed every 30s. Provides `historicalClosingPrices.oneDay` (reference close for change-% calc) and `quote.highest` / `quote.lowest` (session H/L). 15-min delayed but only used for slow-moving fields, so the lag is invisible.
  - **Historical bars (chart only):** [yfinance](https://github.com/ranaroussi/yfinance) REST (`GC=F` / `SI=F` futures, close proxy for spot).

  Why hybrid: Avanza's public web feed is 15-min delayed (`isRealTime: false`), so it can't drive the live price. goldprice.org is near real-time but uses a different reference close, which mismatches Avanza by ~$5. Hybrid combines both — fresh price ticks, exact match on the reference close and H/L that the user sees on avanza.se.
- **Data validation:** Pydantic v2
- **Package manager / runner:** [uv](https://docs.astral.sh/uv/)

## Symbols

Internal IDs: `XAU` (gold), `XAG` (silver). Live data is spot USD price via goldprice.org.

For historical bars, internal IDs map to yfinance futures symbols (`GC=F` / `SI=F`) — see
`HISTORICAL_SYMBOL` in `data/service.py`. Futures track spot within ~0.5%, so the chart's
seeded history smoothly connects with the live spot stream.

## Live quote fields

Tick assembly mixes both feeds (`MetalsService._make_tick` in
`data/service.py`):

- `price` ← goldprice.org `xauPrice` / `xagPrice` (live)
- `change` ← `price − avanza.historicalClosingPrices.oneDay`
- `change_percent` ← `change / avanza.historicalClosingPrices.oneDay * 100`
- `day_high` ← `max(avanza.quote.highest, running max of live ticks)`
- `day_low` ← `min(avanza.quote.lowest, running min of live ticks)`
- `time` ← goldprice.org `ts` (epoch ms → UTC datetime)

Avanza orderbook IDs in `AVANZA_ORDERBOOK`: gold = `18986` (GOLDSP),
silver = `18991` (SILVERSP). Listing metadata labels them as `SEK` but
the numbers are USD/oz — confirmed against the live site.

The chart's "today" view still uses **Europe/Stockholm midnight** as its
x-axis origin (purely a display choice, see `data/session.py` helpers
used from `app.py`).

## Repository Layout

```
src/goldsilver/
  __main__.py        # python -m goldsilver entry
  app.py             # Textual App definition + main()
  data/
    service.py       # MetalsService — live WS + historical REST
    models.py        # Pydantic Tick, Bar models
  widgets/
    price_panel.py   # Per-metal stats panel
    chart.py         # Live-updating plotext chart widget
  styles/
    app.tcss         # Textual CSS (compiled at runtime via CSS_PATH)
pyproject.toml
uv.lock
```

## Run

```bash
uv sync                  # install deps
uv run goldsilver        # launch the TUI
```

Quit with `q`. See in-app footer for other keybindings.

## Conventions

- **No comments** explaining what the code does — only why if non-obvious.
- **Pydantic models** for any data crossing a boundary (WS payloads, REST responses).
- **Reactive widgets** — use Textual's `reactive` attributes, never manually call `refresh()` from outside the widget.
- **Async-first** — all I/O (yfinance WS, HTTP) runs in Textual workers, never blocks the event loop.
- **Latest stable versions** — never pin to old majors. Verify with `uv tree` after adding deps.

## What NOT to do

- Don't commit `.env` files or any credentials.
- Don't add a backend, REST server, or persistence layer — this is a single-process TUI.
- Don't parse yfinance responses with `.get(...)` chains — define a Pydantic model.
- Don't drop either feed of the hybrid without thinking through the tradeoff. Avanza alone
  is 15-min delayed; goldprice.org alone uses a different reference close and mismatches the
  Avanza app's % change by ~0.1–0.2 pp. The hybrid exists because neither single source
  satisfies both "real-time" and "matches the Avanza app".

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan
<!-- SPECKIT END -->
