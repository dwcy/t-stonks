# Phase 1 Data Model: Shared `marketcore` Layer + `quantum` App

This feature is primarily a **structural / packaging** change; it introduces few new
runtime entities. Most "entities" are reused, relocated Pydantic models plus new
configuration/preset shapes for the `quantum` app.

## 1. Reused models (relocated to `marketcore`, schema unchanged)

| Model | New home | Notes |
|-------|----------|-------|
| `Tick` | `marketcore/models.py` | spot tick (symbol, price, time, change, change_percent, day_high, day_low, prev_close) |
| `Bar` | `marketcore/models.py` | OHLCV bar |
| `StockQuote` | `marketcore/models_macro.py` | drives ETF tiles + stock grid + quantum panel |
| `NewsItem` | `marketcore/models_macro.py` | one news entry (source, title, url, published) |
| `Signal` | `marketcore/models_macro.py` | strategy output |
| `FxRate`, `CommodityQuote`, … | `marketcore/models_macro.py` | unchanged, used by goldsilver |

`GOLD = "XAU"`, `SILVER = "XAG"`, `SYMBOLS` stay **out** of `marketcore`; they remain in
`goldsilver/data/models.py`, which re-exports `Tick`/`Bar` from `marketcore` (facade).

## 2. New / parameterized shared shapes

### 2.1 `PollingService` (base class, `marketcore/services/base.py`)
Not a data model but the shared contract every service satisfies:
- `start() -> None`
- `async stop() -> None`
- `async refresh_now() -> None`
- abstract `async _refresh_once(client) -> None` (implemented per service)
- holds `handler`, `stale_handler`, `refresh_interval_s`, `loop_name`, `_stop` Event.

### 2.2 News feed entry (now injected)
```
FeedEntry = tuple[NewsSource, str]   # (source label, RSS URL)
NewsService(feeds: Sequence[FeedEntry], handler=..., stale_handler=..., *, refresh_interval_s=..., max_items=..., per_source_cap=...)
```

### 2.3 Per-app paths (`marketcore/paths.py`)
```
config_base(app_name: str) -> Path        # %APPDATA%/<app> or $XDG_CONFIG_HOME/<app>
settings_path(app_name: str) -> Path       # config_base/settings.json
trades_path(app_name: str) -> Path         # config_base/trades.json
reports_dir(app_name: str) -> Path         # config_base/reports/
```
Validation: `app_name` is a non-empty filesystem-safe slug (`[a-z0-9_-]+`).

## 3. `quantum` app entities

### 3.1 `QuantumSettings` (Pydantic, `quantum/data/settings.py`)
Mirrors `goldsilver`'s settings pattern, scoped to quantum. Minimum fields:

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `etf_tickers` | `list[str]` | `["QTUM", "QTUM"]`* | headline ETF tiles |
| `stock_tickers` | `list[str]` | `["IONQ","RGTI","QUBT","QBTS","ARQQ"]` | pure-play stock grid |
| `news_enabled` | `bool` | `true` | toggle news feed |
| `accent_color_name` | `str` | `"quantum-violet"` | tile accent preset key |
| `refresh_interval_s` | `float` | `60.0` | stock/ETF poll cadence |

\* the second ETF is finalized at implementation from the preset list in §3.3
(distinct from QTUM); placeholder shown to avoid asserting a specific second ETF here.

Persisted via `marketcore.paths.settings_path("quantum")`.

### 3.2 Quantum news feeds (`quantum/data/news_feeds.py`)
`QUANTUM_NEWS_FEEDS: tuple[FeedEntry, ...]` — Google-News RSS topic queries + a vendor
feed, no API key:

| Source label | URL pattern |
|--------------|-------------|
| `QuantumIns` | `https://news.google.com/rss/search?q=when:24h+site:thequantuminsider.com&hl=en-US&gl=US&ceid=US:en` |
| `QC-General` | `https://news.google.com/rss/search?q=when:24h+%22quantum+computing%22&hl=en-US&gl=US&ceid=US:en` |
| `QC-Market`  | `https://news.google.com/rss/search?q=when:24h+(IonQ+OR+Rigetti+OR+QTUM+OR+%22quantum+stock%22)&hl=en-US&gl=US&ceid=US:en` |
| `QC-Research`| `https://news.google.com/rss/search?q=when:24h+(%22quantum+computing%22+breakthrough)&hl=en-US&gl=US&ceid=US:en` |

Reuses the same `NewsItem` model and parsing path as `goldsilver`.

### 3.3 Quantum presets (`quantum/data/presets.py`)
| Preset | Members |
|--------|---------|
| `ETF_DEFAULTS` | quantum-themed ETFs (e.g. `QTUM`, plus one peer) |
| `PUREPLAY_DEFAULTS` | `IONQ`, `RGTI`, `QUBT`, `QBTS`, `ARQQ` (extensible) |
| `ACCENT_PRESETS` | `{"quantum-violet": (155, 89, 255), "quantum-cyan": (0, 200, 220), ...}` |

All treated as editable defaults, not hardcoded behaviour.

## 4. Relationships

```
App (goldsilver | quantum)
 ├── reads/writes  → marketcore.paths.settings_path(app_name)
 ├── instantiates  → marketcore.services.* (PollingService subclasses)
 │                     ├── StockService(tickers)      → StockQuote → StockTile / ETF tile
 │                     └── NewsService(feeds)          → NewsItem  → news panel
 └── renders        → marketcore.widgets.* (PriceChart, StockTile, …)

goldsilver additionally:
 └── MetalsService(PollingService) → Tick (goldprice.org + Avanza hybrid) → MetalPanel
```

## 5. State & validation rules

- No new persistent state machine. Each app's settings file is independent.
- `marketcore` holds **zero** module-level constants tied to a specific app's symbols,
  feeds, or config segment (enforced by FR-1 + the import-direction contract).
- Symbol/ticker lists are inputs, never invariants — services degrade to the stale
  handler on fetch failure (existing behaviour, unchanged).
