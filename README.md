# t-stonks — live metals, macro signals & AI-assisted market reports

<img width="1725" height="2007" alt="image" src="https://github.com/user-attachments/assets/04baccf9-e7a3-492a-a3da-9be0ee227f2e" />

`t-stonks` is a fast terminal dashboard for tracking **gold, silver, macro drivers, market news, stocks, futures, FX and trading signals** in one focused TUI.

It is built for people who actively follow precious metals and related equities, especially when gold, silver, USD, real yields, copper, oil, indexes and market headlines all move at the same time.

The goal is simple:

> See what matters while the market is moving.

---

## What it gives you

* **Live gold & silver tracking**

  * Real-time spot prices for XAU and XAG.
  * Live-updating terminal charts.
  * Day high, day low, change and percentage move.

* **Hybrid market-data model**

  * Live spot price from `goldprice.org`.
  * Reference close and session high/low from Avanza.
  * Historical bars through `yfinance`.

* **Macro dashboard**

  * FX tiles such as USDSEK, CADSEK and EURSEK.
  * Commodities such as copper, Brent, BTC and DXY.
  * Gold/silver ratio.
  * Real-yield tile support.

* **Stock and market context**

  * Configurable stock watchlist.
  * OMX strip.
  * Futures strip.
  * Market news panel.
  * Optional Stocktwits, insider-trade and Congress-trade panels.
  * Follows Trumps outrage.
    

* **Trading workflow tools**

  * Price alerts.
  * Chart zoom modes.
  * Crosshair and pinning.
  * Optional trade simulator.
  * Custom signal visibility and parameters.

* **Claude-powered stock-analysis reports**

  * Generate self-contained HTML reports.
  * Run manually from the TUI or headless from a scheduler.
  * Gold and silver are pinned by default.
  * Add your own stock tickers for recurring analysis.

---

## Why this exists

Most market dashboards are either too generic, too slow, or spread across too many browser tabs.

`t-stonks` is built around a metals-focused workflow:

* gold and silver are the core instruments;
* macro context is visible next to price action;
* related stocks can be tracked in the same view;
* reports can be generated directly from the workflow;
* everything runs locally in your terminal.

No heavy web app. No backend. No database. Just a focused local market cockpit.

---

## Install and run

```bash
uv sync
uv run goldsilver
```

Quit with `q`.

---

## Main controls

| Key | Action           |
| --- | ---------------- |
| `q` | Quit             |
| `p` | Plot/settings    |
| `t` | Trade simulator  |
| `g` | Reports          |
| `a` | Alerts           |
| `r` | Refresh          |
| `z` | Cycle zoom       |
| `h` | Cycle chart mode |
| `x` | Toggle crosshair |

---

## Hourly AI stock-analysis reports

`t-stonks` includes an in-app report engine that generates HTML market reports through the Claude CLI.

The report framework is designed to avoid lazy market takes. Instead of simply claiming that a macro driver is bullish or bearish, it checks the assumption against the market’s actual reaction.

Examples:

* Is gold rising because the dollar is falling?
* Is silver following real yields, copper, or risk appetite?
* Is a mining stock moving with bullion or diverging?
* Are the obvious macro narratives actually confirmed by price action?

Open reports from the TUI:

1. Run the app.
2. Press `g`.
3. Add or remove tickers.
4. Generate now or enable hourly automation.
5. Open the finished HTML reports in your browser.

Reports are written to:

```text
reports/<date>/<time>-<ticker>.html
reports/index.html
```

The `reports/` folder is git-ignored.

---

## Headless report generation

Run the report pipeline without opening the TUI:

```bash
uv run python -m goldsilver.reports --all --once
```

Generate reports for specific instruments:

```bash
uv run python -m goldsilver.reports --ticker XAU --ticker XAG --ticker NVDA --once
```

Generate machine-readable output:

```bash
uv run python -m goldsilver.reports --all --once --json
```

This is useful for cron, Windows Task Scheduler, or other local automation.

## Example screenshots of the report 
<img width="1530" height="1875" alt="image" src="https://github.com/user-attachments/assets/c875d248-fa01-4854-a5af-82275dc5b4e2" />
<img width="1500" height="1187" alt="image" src="https://github.com/user-attachments/assets/e4056ec7-c568-4161-952f-d3e4e584ab53" />
<img width="1503" height="1493" alt="image" src="https://github.com/user-attachments/assets/5ca2ab3c-d3af-4a2c-8e3f-36d9146b21b8" />
<img width="1506" height="716" alt="image" src="https://github.com/user-attachments/assets/c14756ea-fdf2-46ff-8bbb-81623bac3d29" />

---

## Requirements

* Python `3.12+`
* `uv`
* Internet access for market data
* Optional: Claude CLI for report generation

For AI reports, install and authenticate the Claude CLI:

```bash
claude --version
```

No `ANTHROPIC_API_KEY` is required when using Claude CLI subscription authentication.

---

## Tech stack

* **Python 3.12+**
* **Textual** for the terminal UI
* **textual-plotext** for charts
* **Pydantic v2** for data validation
* **httpx** for async HTTP
* **yfinance** for historical market bars
* **uv** for package management and execution
* **pytest** for tests

---

## Repository structure

```text
src/goldsilver/
  __main__.py          # python -m goldsilver entry
  app.py               # Textual app, bindings and layout
  data/                # market data, settings, signals, services
  reports/             # report generation pipeline
  widgets/             # TUI panels, charts and screens
  styles/              # Textual CSS

specs/
  ...

tests/
  ...
```

---

## Example use cases

`t-stonks` is useful when you want to:

* monitor gold and silver during CPI, PPI, Fed, ECB or jobs-report days;
* track Lundin Gold, Lundin Mining or other metals-related stocks next to bullion;
* watch USDSEK, CADSEK, copper, Brent and BTC in the same terminal;
* generate quick AI-assisted market notes during the trading day;
* keep a local dashboard open without relying on a browser-heavy trading UI.

---

## Safety note

This project is for market monitoring, research and personal workflow automation.

It does **not** place trades.

Generated reports are advisory only and are **not financial advice**.
