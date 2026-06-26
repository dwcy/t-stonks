# Quickstart: `marketcore` + `goldsilver` + `quantum`

## Install

```bash
uv sync          # one venv, one lockfile; builds marketcore + goldsilver + quantum
```

## Run the apps

```bash
uv run goldsilver     # the existing gold & silver dashboard (unchanged)
uv run quantum        # the new quantum ETF + stocks + news dashboard
```

Quit either with `q`. Keybindings are in the footer.

## What each app stores, and where

| App | Config dir (Windows) | Config dir (POSIX) |
|-----|----------------------|---------------------|
| goldsilver | `%APPDATA%\goldsilver\` | `$XDG_CONFIG_HOME/goldsilver/` |
| quantum    | `%APPDATA%\quantum\`    | `$XDG_CONFIG_HOME/quantum/`    |

They never touch each other's `settings.json`.

## Editing the quantum watchlist

Defaults live in `src/quantum/data/presets.py`. To change tickers without code, edit the
generated `quantum/settings.json`:

```jsonc
{
  "etf_tickers":   ["QTUM", "<peer-etf>"],
  "stock_tickers": ["IONQ", "RGTI", "QUBT", "QBTS", "ARQQ"],
  "news_enabled":  true,
  "accent_color_name": "quantum-violet"
}
```

## Adding a third app on top of `marketcore`

1. Create `src/<app>/` with `__init__.py` (exposing `main`), `__main__.py`, `app.py`.
2. Import shared pieces: `from marketcore.services.stock_service import StockService`,
   `from marketcore.widgets.stock_tile import StockTile`, etc.
3. Use `marketcore.paths.settings_path("<app>")` for config isolation.
4. If the app needs its own news, pass your feed list:
   `NewsService(feeds=MY_FEEDS, handler=...)`.
5. Register the script in `pyproject.toml`:
   ```toml
   [project.scripts]
   <app> = "<app>:main"
   ```
6. `uv sync && uv run <app>`.

## Tests

```bash
uv run pytest                       # full suite (goldsilver + marketcore + quantum)
uv run pytest tests/marketcore      # shared-layer contracts (paths, feed injection, import direction)
uv run pytest tests/quantum         # quantum app mount + render smoke test
```

## Verifying the refactor did no harm

- `uv run goldsilver` looks and behaves exactly as before.
- `python -c "import marketcore"` succeeds with no app on the path.
- `settings_path("goldsilver")` resolves to the pre-refactor location (regression test).
