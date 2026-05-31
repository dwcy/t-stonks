# Quickstart — 24-hour Sliding Chart + Stock Mini-Tiles

## Try the feature

```bash
uv sync
uv run goldsilver
```

On launch you should see:

- **Top strip** — USD/SEK · CAD/SEK · BRENT (unchanged)
- **OMX strip** — OMX30 weekly + daily lights (unchanged)
- **NEW: Stock mini-tile row** — 4 tiles in one row by default:
  `LUG.TO  ▲ +1.42%`, `LUG.ST`, `LUMI.ST`, `LUNR.V`, each with a 4-row sparkline.
- **Gold and silver panels** — charts now show the **rolling last 24 hours** with the live
  edge on the right. Hour ticks (`|`) and half-hour ticks (smaller `|`) along the bottom.

## Keybindings

| Key       | Action                                                    | Mode         |
|-----------|-----------------------------------------------------------|--------------|
| `h`       | Toggle chart mode: live ↔ history                         | both         |
| `z`       | Cycle chart zoom: 24h → 3h → 1h → 24h                     | live only    |
| `x`       | Toggle crosshair mode                                     | live only    |
| `←` / `→` | Move crosshair one sample (when active)                   | live only    |
| `PgUp` / `PgDn` | Move crosshair by ~1 hour                           | live only    |
| `Enter`   | Pin the crosshair sample                                  | live only    |
| `c` (in chart) | Clear pinned samples                                 | live only    |
| `q`       | Quit                                                      | both         |
| `r`       | Refresh feeds                                             | both         |
| `p`       | Plot settings (zoom, mode, timeframe all exposed here)    | both         |

## Edit your stock tickers

Find `settings.json`:

- **Windows**: `%APPDATA%\goldsilver\settings.json`
- **macOS / Linux**: `$XDG_CONFIG_HOME/goldsilver/settings.json` (default
  `~/.config/goldsilver/settings.json`)

Open it and edit the `stock_tickers` array:

```json
{
  "stock_tickers": ["LUG.TO", "LUG.ST", "LUMI.ST", "LUNR.V", "BOL.ST", "AAPL"]
}
```

Restart the TUI. Up to 6 tickers fit on one row; more wrap to a second row.

**Format**: raw yfinance symbols. Use the same suffix you'd use on Yahoo Finance:
`.TO` (Toronto), `.ST` (Stockholm), `.L` (London), no suffix for US listings.

## Verify the feature is working

### Rolling 24 h check
1. Note the leftmost x-tick label on the gold chart (e.g. `14`).
2. Wait until the local hour rolls over.
3. The leftmost label has advanced by one hour; the rightmost is the new current hour.

### Zoom check
1. Press `z` — chart shrinks to last 3 hours, x-ticks dense.
2. Press `z` again — last 1 hour, x-ticks every 15 min with hour-mark `|` at the boundary.
3. Press `z` again — back to 24 h.

### Crosshair check
1. Press `x` — vertical line appears at the rightmost sample, subtitle shows
   `HH:MM  price`.
2. Press `←` a few times — line moves left, subtitle updates.
3. Press `Enter` — gold dot pinned at that x position.
4. Press `x` — crosshair dismissed, pinned dot remains.
5. Press `c` — pin removed.

### Stock-tile check
1. Both Lundin Gold tickers should show similar % moves (same company, different
   currencies). The absolute prices differ (CAD vs SEK).
2. `LUNR` shows USD price.
3. Edit `settings.json`, remove `LUNR`, restart — three tiles render at 1/3 width each.

## Common issues

- **Stock tile shows `--`**: ticker is invalid, market is closed and no prior close exists,
  or yfinance rate-limited the symbol. Try a different ticker or wait one refresh cycle.
- **`LUG.ST` not updating during US session**: Stockholm exchange is closed; the tile shows
  the last close until the next Stockholm session.
- **Mouse-wheel zoom doesn't work**: some terminals do not forward wheel events to Textual.
  Use `z` instead.
- **Half-hour ticks missing**: terminal font may not render `|` at scatter-marker size;
  ticks are still there logically, just visually compressed.
