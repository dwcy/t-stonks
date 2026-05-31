# Phase 0 — Research: 24-hour Sliding Chart + Stock Mini-Tiles

## Open questions resolved

### Q1. Does `textual-plotext` (plotext-on-Textual) support mouse-wheel zoom and a movable crosshair?

**Decision**: Plotext itself is a raster terminal-plot library; it does **not** expose a
native mouse-wheel handler, and the Textual wrapper (`textual-plotext.PlotextPlot`) does
not propagate `MouseScrollUp` / `MouseScrollDown` to plotext. We must implement zoom and
crosshair at the **Textual widget level**, calling `self.plt.xlim(...)` and re-running
`_redraw()` ourselves.

- **Zoom**: maintain a `_zoom: Literal["24h","3h","1h"]` in `PriceChart`, and in
  `_redraw()` compute `xmin = (now - window) - origin` / `xmax = now - origin` in minutes
  and call `self.plt.xlim(xmin, xmax)`. The visible window slides because we recompute
  `now` on every tick.
- **Mouse wheel**: Textual exposes `MouseScrollUp` / `MouseScrollDown` events on the
  parent widget; the chart can override `on_mouse_scroll_up/down` to cycle zoom levels.
  Confirmed pattern in Textual 8.x.
- **Crosshair**: plotext has `vline(x, color)` which we can use to render the vertical
  guide; the price + time label is rendered as a separate `Static` overlay (or in the
  chart's `border_subtitle` for low effort). Arrow keys captured via `BINDINGS` on the
  chart widget when `_crosshair_active`.

**Rationale**: Keeps the existing chart library (no new dep), all interaction handled in
Textual where we already control state.

**Alternatives considered**:
- *Replace `textual-plotext` with a custom braille renderer.* Rejected — too much work for
  the same end-result and existing chart code already works.
- *Use `plotext.interactive()`.* Rejected — that hijacks stdin and is incompatible with
  a Textual host process.

---

### Q2. Which yfinance tickers cover "Lundin Gold from all markets", "Lundin Mining", and "LunR"?

**Decision**: Default `stock_tickers` ships with:

| Ticker     | Company / Exchange                                 | Currency |
|------------|----------------------------------------------------|----------|
| `LUG.TO`   | Lundin Gold Inc., Toronto Stock Exchange           | CAD      |
| `LUG.ST`   | Lundin Gold Inc., Nasdaq Stockholm                 | SEK      |
| `LUMI.ST`  | Lundin Mining Corp., Nasdaq Stockholm              | SEK      |
| `LUNR.V`   | Lundin Royalties Corp., TSX Venture Exchange       | CAD      |

**Rationale**:
- Lundin Gold's primary listing is **LUG on TSX**; secondary listing is **LUG on Nasdaq
  Stockholm**. The user explicitly said "from all markets" → ship both.
- Lundin Mining is primarily Toronto (LUN.TO) but the user is Swedish-based and the
  Stockholm depository listing (`LUMI.ST`) trades in SEK, matching the other Lundin Gold
  Stockholm ticker. **Decision**: ship `LUMI.ST` only by default; user can add `LUN.TO`
  manually if they want the Toronto print.
- "LunR" was clarified by the user (2026-05-30) to be **Lundin Royalties**, trading on
  the TSX Venture Exchange as `LUNR.V` (Yahoo Finance URL:
  `https://finance.yahoo.com/quote/LUNR.V/`). The previous assumption (NASDAQ:LUNR /
  Intuitive Machines) was wrong and is removed. Verified `LUNR.V` returns valid CAD-priced
  daily bars via `yfinance.Ticker('LUNR.V').history(...)`.

**Alternatives considered**:
- *Hard-code only one Lundin Gold listing.* Rejected — user said "all markets".
- *Use ISIN-based lookup.* Rejected — yfinance is symbol-based; ISIN requires another
  upstream.
- *Ship `LUNR` (NASDAQ:Intuitive Machines) as default and let the user fix it later.*
  Rejected — would render a misleading tile with a wrong company name; user confirmed
  `LUNR.V` instead.

---

### Q3. yfinance polling cadence + payload shape for `LUG.TO / LUG.ST / LUMI.ST / LUNR`

**Decision**: Reuse the existing `OmxService` pattern.
- Cadence: **60 seconds** (`STOCK_REFRESH_INTERVAL_S = 60.0`).
- Per refresh: one async batch via `asyncio.to_thread`. Each ticker fetched via
  `yf.Ticker(symbol).history(period="2d", interval="5m")`. This gives both the previous
  daily close (last bar of the prior day) and today's 5-min intraday series for the
  sparkline.
- Previous close fallback: if 5-min payload's first bar's day != current-day, use first
  bar's close as `previous_close`. Otherwise call `yf.Ticker(symbol).history(period="5d",
  interval="1d")` and take the second-to-last close.
- Empty / failed batch → emit `stale` event with `time.now()`.

**Rationale**: 60 s matches `OmxService`. yfinance handles batch fetches in a thread, so
the event loop is not blocked. 5-min intervals are enough for a 12-point sparkline in a
typical pre-market-to-mid-day window.

**Alternatives considered**:
- *1-min intraday.* yfinance free intraday `1m` is rate-limited and only returns the last 7
  days. 5-min is more reliable and the sparkline only needs ~30 points anyway.
- *Polling every 10 s.* Excessive for stock tiles that don't have a live spot equivalent;
  60 s is the same cadence the user already accepts for OMX.

---

### Q4. Keep the multi-day timeframe picker (`today / 5d / 1mo / 3mo`) or replace?

**Decision**: **Keep** the multi-day picker as a separate **history mode**, layered
on top of the new live "rolling 24 h + zoom" mode. The chart has two top-level modes:

- **Live mode** (default): rolling 24 h window with `z` cycling 24 h / 3 h / 1 h zoom,
  crosshair, pins, live tick at the right edge. Persisted via `chart_zoom`.
- **History mode**: the existing `today / 5d / 1mo / 3mo` picker, no rolling window
  behaviour, no live-tick ingestion (the chart shows the full yfinance bar history at the
  chosen interval). Persisted via `timeframe_index` (existing field — kept).

Mode switch is a separate keybinding (suggested `h` to toggle live ↔ history). When in
history mode the `z` / `x` / pin / mouse-wheel bindings are suppressed; the
timeframe-radio in `PlotSettings` is enabled. When in live mode, the timeframe-radio is
hidden and the new zoom-radio is shown.

**Rationale** (revised — user explicitly requested history mode):
- Live mode answers "what is happening right now"; history mode answers "what did the
  last quarter look like". Both are useful and the user uses both.
- Keeping them as **distinct modes** (not stacked axes) preserves a single mental model
  per mode — no zoom-on-3mo edge cases, no crosshair on 1d candles.
- yfinance multi-day data is already in `MetalsService.fetch_history()`; nothing new to
  fetch.

**Implementation impact**:
- `AppSettings.timeframe_index` is **kept** (was tagged for removal pre-decision).
- `AppSettings.chart_mode: Literal["live", "history"] = "live"` — new field, persisted.
- `app.py` `_seed_panel()` branches on mode: live → seed last 24 h then start live ticks;
  history → seed yfinance bars for the selected timeframe and **do not** call
  `add_point()` from `_on_tick`.
- `widgets/chart.py` gains `set_mode(mode)`; rendering paths for the two modes share the
  same `_redraw()` but use different x-range logic (rolling window vs. show-all-bars).

**Alternatives considered**:
- *Replace with zoom only.* Rejected by user.
- *Keep both as orthogonal axes (zoom × timeframe).* Rejected — combinatorial UX, and the
  user wants them as distinct modes, not stacked axes.

---

### Q5. How do we render two tick sizes on a plotext x-axis?

**Decision**: Plotext's `xticks(ticks, labels)` accepts one set of ticks; we cannot
natively render two heights. We render the "small" half-hour marks as **part of the
labels** themselves — using `'|'` (full-height) for hour marks and `''` (no mark) for
half-hour marks, then drawing the half-hour marks via a separate plotext layer
(`plt.scatter` with a `marker='|'` symbol at y=plot_min). For 1 h zoom: hour mark at the
hour boundary, small marks at :15, :30, :45.

**Rationale**: Plotext is single-axis. Using a scatter-based marker layer pinned at the
chart's y-floor gives us a second visual tier without forking plotext.

**Alternatives considered**:
- *Render ticks via custom CSS in Textual border.* Rejected — chart bottom is part of the
  plotext canvas, not the Textual border.
- *Drop the half-hour ticks.* Rejected — explicit user requirement.

---

### Q6. Crosshair "click on dot" support without mouse events

**Decision**: Hybrid.
- Without mouse: arrow-key crosshair (`x` to activate, `←/→` to move, `Enter` to pin,
  `Esc` to dismiss). This is the primary path.
- With mouse: clicking inside the chart area while crosshair mode is active sets the
  crosshair to the column under the click; double-click pins.

**Rationale**: Keyboard-only is the canonical control (matches the rest of the TUI's
accessibility). Mouse is an enhancement layered on the same state machine.

**Alternatives considered**:
- *Pure mouse.* Rejected — terminal mouse support is patchy.
- *No pinning at all.* Rejected — user explicitly asked to "press one of the dots".

---

### Q7. Sparkline rendering in mini-tiles

**Decision**: Use `textual-plotext.PlotextPlot` set to height `3` (Textual rows) with
braille marker, no axes, no labels. Wrap in a `Static` for the "ticker / price / %"
header line above the sparkline; total tile height = 4 rows. This matches the visual
weight of the FX tiles plus enough vertical room for a meaningful sparkline.

**Rationale**: We already depend on plotext via `textual-plotext`. Reusing it for
sparklines keeps the rendering stack uniform.

**Alternatives considered**:
- *Hand-rolled braille mini-renderer.* Rejected — `textual-plotext` already does this
  competently.
- *No sparkline, just price + %.* Rejected — sparkline is what makes the row scannable.

---

### Q8. Settings migration

**Decision**: Additive only. `AppSettings` gains `stock_tickers: list[str]` and
`chart_zoom: Literal["24h","3h","1h"]`; `timeframe_index` is removed from the dataclass
fields. The `load()` method already ignores unknown keys (`allowed = {f.name for f in
fields(cls)}`), so old settings files with a `timeframe_index` value will silently drop
it. No data loss; user's other preferences (colors, signal params, etc.) preserved.

**Rationale**: The loader's existing `clean = {k: v for k, v in raw.items() if k in
allowed}` filter handles deprecated fields safely. No migration code needed.

**Alternatives considered**:
- *Bump a `settings_version` field.* Rejected — overengineering for an additive change.

## Summary table

| ID | Decision                                                          | Affects file(s)                               |
|----|-------------------------------------------------------------------|-----------------------------------------------|
| Q1 | Implement zoom + crosshair at Textual layer; use `plt.xlim`       | `widgets/chart.py`                            |
| Q2 | Default tickers: `LUG.TO`, `LUG.ST`, `LUMI.ST`, `LUNR`            | `data/settings.py`                            |
| Q3 | 60 s yfinance polling, `period=2d interval=5m`                    | `data/stock_service.py` (new)                 |
| Q4 | Keep timeframe picker as separate "history" mode (live↔history)   | `app.py`, `widgets/plot_settings.py`, `settings.py` |
| Q5 | Render half-hour ticks as scatter markers at chart's y-floor      | `widgets/chart.py`                            |
| Q6 | Keyboard-first crosshair, mouse as enhancement                    | `widgets/chart.py`, `app.py` (BINDINGS)       |
| Q7 | Reuse `PlotextPlot` for mini-tile sparklines, height 4 rows       | `widgets/stock_tile.py` (new)                 |
| Q8 | Additive settings change; deprecated fields silently dropped      | `data/settings.py`                            |
