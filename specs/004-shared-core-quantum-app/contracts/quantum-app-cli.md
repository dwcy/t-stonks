# Contract: `quantum` App — CLI & UI

## Command

```bash
uv run quantum
```

Resolves to the `quantum = "quantum:main"` console script in `pyproject.toml`.
`quantum/__init__.py` exposes `main`; `quantum/__main__.py` enables
`python -m quantum`.

### Arguments
- `--force-wide` (optional) — mirror `goldsilver`'s wide-layout flag if present.
- No required arguments. No API keys. No network endpoints configured by the user.

### Exit
- `q` quits the TUI cleanly (Textual default binding shown in footer).
- Non-zero exit only on unhandled startup error (e.g. missing dependency).

## UI contract (on launch)

| Region | Content | Backing service / widget |
|--------|---------|--------------------------|
| Headline tiles | Quantum ETF(s) live price + change% | `StockService(etf_tickers)` → ETF tile (`StockTile` or `PriceChart` panel) |
| Stock grid | Pure-play quantum stocks, live quote + change% + sparkline | `StockService(stock_tickers)` → `StockTile` |
| News panel | Quantum-computing headlines, newest first | `NewsService(QUANTUM_NEWS_FEEDS)` → `NewsItem` list |
| Footer | Keybindings | Textual footer |

### Behavioural guarantees
- All data fetched in async Textual workers; the UI never blocks on network.
- A failing feed/ticker shows a stale indicator (reused stale-handler path), not a crash.
- Settings persist to `marketcore.paths.settings_path("quantum")`, independent of
  `goldsilver`.
- Default watchlists come from `quantum/data/presets.py` and are user-editable via the
  settings file.

## Acceptance checks

- `uv run quantum` opens the TUI without traceback; `q` exits 0.
- Smoke test (`App.run_test()` + `pilot.pause()`) mounts the app and renders the three
  regions without error.
- With network mocked/unavailable, the app still mounts and shows stale states (no
  exception).
- `quantum` writes only under its own config dir; running it does not modify
  `goldsilver` settings.
