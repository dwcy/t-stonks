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

Multi-app monorepo: one `pyproject.toml`, three packages under `src/`. `marketcore`
is the shared lower layer (symbol-agnostic); `goldsilver` and `quantum` are apps built
on it. `marketcore` must never import an app package (guarded by
`tests/marketcore/test_import_direction.py`).

```
src/
  marketcore/          # shared lower layer (imported by every app)
    models.py          # Tick, Bar
    models_macro.py    # FX/commodity/stock/news/calendar/social models
    http.py            # make_client() httpx factory
    session.py         # tz-parameterized now/date/midnight helpers
    paths.py           # config_base(app_name) + per-app settings/trades/reports paths
    fsutil.py          # atomic_write_text()
    services/
      base.py          # PollingService — shared start/stop/refresh loop
      stock_service.py # StockService (yfinance), register_names()
      news_service.py  # NewsService(feeds=...) — RSS feed list injected
    widgets/
      chart.py         # PriceChart (plotext)
      stock_tile.py    # StockTile live quote + sparkline
      format.py        # color palette + format_age()
  goldsilver/          # gold & silver app (re-points to marketcore via facades)
    app.py             # GoldSilverApp + main()
    data/
      service.py       # MetalsService — goldprice.org + Avanza hybrid (metal-specific)
      news_feeds.py    # goldsilver's RSS feed list, injected into NewsService
      settings.py      # AppSettings; paths via marketcore.paths("goldsilver")
    widgets/metal_panel.py
    styles/app.tcss
  quantum/             # quantum ETFs + pure-play stocks + news app
    app.py             # QuantumApp + main()
    data/presets.py    # ETF + pure-play tickers, accent colours, name overrides
    data/news_feeds.py # QUANTUM_NEWS_FEEDS
    data/settings.py   # QuantumSettings; paths via marketcore.paths("quantum")
    widgets/news_panel.py
    styles/app.tcss
pyproject.toml
uv.lock
```

Older `goldsilver` modules (fx/commodity/futures/calendar/congress/insider/yields
services, strategy/trade/report engines) still live under `goldsilver/` and import the
shared leaves from `marketcore`; they can be migrated into `marketcore` incrementally.

## Run

```bash
uv sync                  # install deps
uv run goldsilver        # launch the gold & silver TUI
uv run quantum           # launch the quantum ETFs/stocks/news TUI
```

Each app stores settings under its own OS config dir (`%APPDATA%/<app>` /
`$XDG_CONFIG_HOME/<app>`). Quit with `q`. See in-app footer for other keybindings.

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
at `specs/004-shared-core-quantum-app/plan.md`.
<!-- SPECKIT END -->
