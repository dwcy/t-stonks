# Feature Specification: 24-hour Sliding Chart + Stock Mini-Tiles

**Feature Branch**: `001-macro-economic-calendar` (continuation feature, separate spec)
**Created**: 2026-05-30
**Status**: Draft
**Input**: User description: "For the plots they should fill the entire area with 24hours. default 00:00 -> 24:00 and the entire graph should slide so the latest hour is latest and 24h back. Important to also display every hour as a larger | and every half hour as a smaller | in the bottom. I should be able to slide a timeline to se exact time aand press one of the dots. I zoom in with scroll zoom if possible or show latest 3 or 1 hour. that fills the entire graph is something we need. Besides that we need a smaller variantes of graphs where we can follow stocks and the stocks to follow should be in the existing config file for the app and edititable what I want, and it should be 6 per row and stretch to fit if less than 6. The mini charts should not have eny momentum and no plot chart. And in the config I want to have Lundin Gold from all markets, Lundin Mining, LunR"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Rolling 24-hour gold/silver chart (Priority: P1)

The user opens the TUI mid-afternoon. The gold and silver charts each show the full last
24 hours of price action: the **right edge** is the live tick (now), the **left edge** is
exactly 24 hours ago. As new ticks arrive and minutes pass, the entire visible window slides
left so the live edge stays at "now" — the user always sees the most recent hour plus the
preceding 23. The x-axis has a tick mark for every full hour (large `|`) and every half-hour
(smaller `|`) along the bottom, with the hour numbers labelled.

**Why this priority**: The current chart's x-axis origin is "Stockholm midnight today", which
means after midnight the panel is almost empty. A rolling 24-hour view always shows a full
day of context regardless of when the user opens the app or how long it stays open.

**Independent Test**: Launch the TUI at any time of day. Within 5 s the gold chart fills the
panel width with bars covering ~24 h, the rightmost x-tick label equals the current local hour,
and the leftmost label equals (now − 24 h) rounded to the nearest hour. Hour ticks (`|`) and
half-hour ticks (smaller `|`) are visible along the bottom. Leave the TUI open for ≥10 min;
the right edge moves with wall-clock time and old samples scroll off the left edge.

**Acceptance Scenarios**:

1. **Given** the TUI is launched at 14:23 local, **When** the gold chart renders,
   **Then** the visible window covers 14:23 yesterday → 14:23 today, the right edge is the
   live tick, and the bottom axis shows hour ticks at every full hour and half-hour ticks
   between them.
2. **Given** the TUI has been running and the clock crosses 15:00, **When** the user looks
   at the chart, **Then** the leftmost sample is now 15:00 yesterday (no longer 14:23) and
   the rightmost sample is the latest live tick — the entire visible window has slid one
   minute to the right.
3. **Given** the chart fills the panel width, **When** the user looks at the bottom axis,
   **Then** every full-hour tick is visibly taller/heavier than the surrounding half-hour
   ticks, so the hour grid is pre-attentively distinguishable.

---

### User Story 2 - Zoom to 3 h or 1 h to fill the chart (Priority: P1)

The user wants a tighter view to see intraday structure. They can switch the chart's visible
window to **3 hours** or **1 hour**. When they do, the visible window covers exactly that
range from the live edge backwards, and the chart's x-axis still has the same large-vs-small
hour/half-hour tick convention (the small ticks become 15-minute marks at 1 h zoom). The
chart always uses the **full panel width** — never leaves dead space.

**Why this priority**: Zoom is the natural follow-up to a wider rolling view: you scan the
day, then drill into the last hour. Without zoom, the 24 h view can't show short-term action.

**Independent Test**: From the default 24 h view, switch to 3 h and the visible window covers
~now-3h → now with the live tick on the right edge. Switch to 1 h; window covers ~now-1h →
now. In each case the bottom tick density adjusts so the bottom axis is still readable (hour
ticks are large, intermediate ticks are small) and the data fills the full panel width.

**Acceptance Scenarios**:

1. **Given** the chart is on default 24 h, **When** the user activates the 3 h zoom,
   **Then** the visible window changes to the last 3 hours with the live edge on the right,
   and the bottom axis labels each full hour (3 labels: e.g. 12, 13, 14) with smaller marks
   between them.
2. **Given** the chart is on 24 h, **When** the user activates 1 h zoom, **Then** the
   visible window is the last 1 hour, with small ticks every 15 min and large ticks at the
   full-hour boundary inside the window.
3. **Given** the user mouse-wheel-scrolls inside the chart area on a terminal that supports
   it, **Then** scrolling up zooms in (24 h → 3 h → 1 h), scrolling down zooms out. On
   terminals without mouse-wheel support, the same zoom levels are reachable via keyboard
   bindings (see FR-006).

---

### User Story 3 - Slide a crosshair / timeline to read exact price + time (Priority: P2)

The user wants to read off the exact price at a specific moment. They activate a crosshair
mode and move it left/right across the chart. As it moves, a vertical line marks the
hovered timestamp and a tooltip / sidebar field shows the exact `HH:MM` and the price at
that sample. When the user clicks (or presses Enter) on a dot, that sample is "pinned" with
a marker so it stays highlighted after the crosshair moves away.

**Why this priority**: Useful but not blocking the main use case (real-time monitoring). The
24 h roll and zoom are the high-value items; crosshair is for retrospective reading.

**Independent Test**: Activate the crosshair with the documented keybinding. A vertical line
appears in the chart at the rightmost sample with an inline label `HH:MM  price`. Move it
left with arrow keys (and mouse, if supported); the label updates to the sample under the
cursor. Press Enter on one sample; a pinned dot remains on that x position after the
crosshair is dismissed.

**Acceptance Scenarios**:

1. **Given** the user activates crosshair mode, **When** they move it left, **Then** the
   vertical line moves one sample left per keystroke and the timestamp + price label
   updates in real time.
2. **Given** crosshair mode is active and pointed at the 13:42 sample, **When** the user
   presses Enter, **Then** a small dot remains rendered at that x position after the
   crosshair is dismissed.
3. **Given** the user has pinned ≥1 sample, **When** they press the same shortcut a second
   time, **Then** the pin is removed.

---

### User Story 4 - Stock mini-tile row (Priority: P1)

Below the macro-strip and OMX strip, a horizontal row of **stock mini-tiles** shows up to 6
configured stocks side-by-side. Each tile shows: ticker label, last price, day change %,
and a tiny sparkline of today's intraday movement. Tiles are equal-width, stretching to
fill the row if there are fewer than 6 (e.g. 3 tiles each take 1/3 of the row width).

The mini-charts are **not** the full chart widget: no SMA / VWAP / candles, no momentum or
recoil signal markers, no day-reference lines. Just a clean sparkline + price label, so the
row stays compact and low-noise.

**Why this priority**: Mining stocks (Lundin Gold etc.) track the gold price; seeing them on
the same screen is the user's stated goal. Without this row, the gold/silver dashboard does
not give the user the equity exposure picture.

**Independent Test**: Launch the TUI with the default config (3 stocks: Lundin Gold,
Lundin Mining, LUNR). Within 15 s, three equal-width tiles render in one row, each with the
ticker, current price, today's % change with up/down arrow + color, and a sparkline showing
today's intraday move. Edit the config to add a 4th ticker; relaunch — 4 tiles each take
1/4 of the row.

**Acceptance Scenarios**:

1. **Given** the config lists 3 stock tickers, **When** the TUI renders, **Then** exactly
   3 mini-tiles appear in one row, each taking 1/3 of the available row width, with no
   momentum/signal markers on the sparkline.
2. **Given** the config lists 6 stock tickers, **When** the TUI renders, **Then** 6 mini-
   tiles appear in one row, each taking 1/6 of the row width.
3. **Given** the config lists 0 stock tickers, **When** the TUI renders, **Then** the
   stock-row container is hidden (no empty band) so vertical space is reclaimed by the
   chart panels.
4. **Given** the config lists ≥7 stock tickers, **When** the TUI renders, **Then** the
   first 6 fit on row 1 and additional tickers wrap to row 2 at the same per-tile width.

---

### User Story 5 - Configure which stocks to follow (Priority: P1)

The user edits the existing settings file (the same `settings.json` already used by the
app) and adds, removes, or reorders the list of stock tickers to track. On next launch the
mini-tile row reflects the change. The default config ships with the three tickers the user
asked for: **Lundin Gold** (all markets — both Toronto and Stockholm listings), **Lundin
Mining**, and **LUNR**.

**Why this priority**: Without configurability the row is just a hardcoded list; with it
the user can swap in their actual portfolio at any time.

**Independent Test**: Locate `settings.json`, edit `stock_tickers` to e.g.
`["LUG.TO", "LUMI.ST"]`, restart the TUI. The mini-tile row now shows two tiles only,
matching the edit, each stretched to half-width.

**Acceptance Scenarios**:

1. **Given** the user edits `stock_tickers` in `settings.json` to add a new ticker,
   **When** they restart the TUI, **Then** the new ticker appears as a mini-tile with live
   data within 15 s of startup.
2. **Given** the user removes a ticker from `settings.json`, **When** they restart,
   **Then** that tile no longer renders and the remaining tiles stretch to fill the row.
3. **Given** the config contains an invalid / unknown ticker, **When** the TUI launches,
   **Then** the corresponding tile shows a muted `--` placeholder and the others render
   normally — no crash, no blocking other feeds.

---

### Edge Cases

- **Pre-market / off-hours**: Stock mini-tiles render the last available close with a
  "closed" indicator instead of an aggressive arrow color, so the user does not mistake a
  stale close for live action. Sparkline shows the most recent session's intraday line.
- **Lundin Gold dual listing**: The user wants "Lundin Gold from all markets". Resolved by
  shipping both `LUG.TO` (Toronto) and `LUG.ST` (Stockholm) in the default config; each is
  its own tile so the user can compare CAD vs SEK price action.
- **Mouse-wheel scroll not supported by terminal**: Zoom must remain reachable via
  keyboard. Mouse is an enhancement, not a hard requirement.
- **Crosshair on a chart with <2 samples**: Crosshair mode is a no-op (or renders a muted
  hint "no data") rather than crashing.
- **Window resize during live ticks**: The chart re-fits to the new panel width without
  losing the current zoom level or the rolling 24 h window definition.
- **Time crosses midnight**: The 24 h window keeps rolling — the left edge crosses
  "yesterday-yesterday" silently. No special re-segmentation needed (this is a rolling
  window, not a calendar day).
- **DST transitions**: Hour-tick rendering uses local wall-clock minutes since midnight,
  so a 23 h or 25 h DST day still gets correct tick spacing without double-rendering hour
  labels.
- **Sparkline with <2 ticks**: Render a single flat line or dot rather than crashing.
- **Stock feed failure**: Tile keeps last value with a "stale" marker, never crashes, never
  blocks the metals chart or other feeds.

## Requirements *(mandatory)*

### Functional Requirements

#### Chart redesign — rolling 24 h + zoom + crosshair

- **FR-001**: The gold and silver charts MUST display a **rolling 24 h** time window by
  default: right edge = latest live tick, left edge = exactly 24 h before the right edge.
  The window MUST slide continuously as wall-clock time advances; the user MUST never see
  empty space at the right edge or a stale "today only" cut-off after midnight.
- **FR-002**: The chart's bottom axis MUST render **two tick sizes**: a large tick at every
  full local hour, a smaller tick at every half hour. Hour ticks MUST be visually heavier
  than half-hour ticks (taller, bolder, or otherwise pre-attentively distinguishable on a
  monospace terminal).
- **FR-003**: Hour tick labels MUST be the local hour (e.g. `12`, `13`, …, or `HH:MM` if
  panel width allows). Half-hour ticks MUST NOT be labelled (avoid axis clutter).
- **FR-004**: The chart MUST support **three zoom levels** at minimum: 24 h (default), 3 h,
  1 h. Each zoom level MUST keep the right edge anchored to the live tick and MUST fill the
  full panel width with the visible window's data.
- **FR-005**: At the 1 h zoom, half-hour ticks MUST become **15-minute ticks** (so the
  bottom axis stays informative at the smaller window). At 3 h, the half-hour ticks remain
  half-hour.
- **FR-006**: Zoom level MUST be reachable via a documented **keyboard shortcut**
  (suggested `z` to cycle 24 h → 3 h → 1 h → 24 h, or `+` / `-`). Mouse-wheel scroll-zoom
  MUST also be supported when the terminal exposes wheel events to Textual.
- **FR-007**: The chart MUST support a **crosshair / cursor mode**, activated by a
  documented shortcut (suggested `x`). When active, a vertical guide line marks a hovered
  timestamp; a label shows `HH:MM  price` for the sample under the cursor. Arrow keys MUST
  move the crosshair one sample at a time; PgUp / PgDn MUST move by 1 hour (or by the
  visible window's "large step" equivalent).
- **FR-008**: While the crosshair is active, pressing **Enter** (or a documented shortcut)
  MUST pin a marker at the current crosshair position. The pin MUST persist after
  crosshair mode is dismissed and MUST be removable.
- **FR-009**: Zoom changes, crosshair mode, and pins MUST NOT block live tick ingestion;
  the live edge continues advancing in the background. Re-rendering on each tick MUST stay
  smooth at the existing tick cadence (≥1 tick / 5 s).
- **FR-010**: Existing chart features (line vs candle, SMA, VWAP, day-refs, momentum /
  recoil markers) MUST continue to work on the metals charts at all zoom levels. None of
  these are removed by this feature.
- **FR-011**: The chart MUST never render the placeholder "today midnight → live" origin
  used pre-feature; the rolling-24 h origin MUST replace it.

#### Stock mini-tile row

- **FR-012**: The TUI MUST gain a horizontal **stock mini-tile row** placed between the OMX
  strip and the gold/silver panels, rendering one tile per configured stock ticker.
- **FR-013**: Each mini-tile MUST display, at minimum: ticker label, last price, day's
  absolute change, day's change percent, and a **compact sparkline** of today's intraday
  closes. Up / down direction MUST be colored using the same green / red palette as the FX
  tiles and metals panels.
- **FR-014**: Mini-tile sparkline MUST NOT render: SMA, VWAP, candles, day-reference lines,
  momentum or recoil signal markers, or any of the metals-chart overlays. The sparkline is
  a single-line close trace only.
- **FR-015**: The row MUST lay out **up to 6 tiles per row**. With fewer than 6 tickers
  configured, the tiles MUST stretch equally so the row is always fully occupied (each tile
  is `1fr` of `len(tickers) / row` width). With more than 6 tickers, tiles MUST wrap to
  additional rows of 6.
- **FR-016**: An empty `stock_tickers` list MUST hide the row entirely (no blank band).
- **FR-017**: The list of stock tickers MUST live in the existing `settings.json`
  (`stock_tickers: list[str]`). The default list MUST be: `LUG.TO` (Lundin Gold, Toronto),
  `LUG.ST` (Lundin Gold, Stockholm), `LUMI.ST` (Lundin Mining, Stockholm), `LUNR.V`
  (Lundin Royalties, TSX Venture).
- **FR-018**: Stock quotes MUST be fetched from a **free, no-API-key** public source
  (yfinance is already a project dependency and serves intraday + daily data for these
  tickers — confirmed in research.md).
- **FR-019**: Stock quotes MUST be refreshed at a cadence between **60 s and 120 s**
  (matching the OMX strip's existing 60 s cadence). One request batch per refresh covering
  all configured tickers.
- **FR-020**: Stock-fetch failure MUST degrade gracefully: keep last known values with a
  "stale" marker, never crash the TUI, never block other feeds.
- **FR-021**: The mini-tile row MUST respect the existing reactive-widget pattern and
  Pydantic-validation discipline — quotes are validated `StockQuote` Pydantic models, the
  service is an async worker, the tile is a `reactive` widget.

#### Settings + persistence

- **FR-022**: A new field `stock_tickers: list[str]` MUST be added to `AppSettings` with a
  sensible default (see FR-017). The field MUST round-trip through `settings.json` and be
  editable by hand without breaking the loader.
- **FR-023**: A new field `chart_zoom: Literal["24h", "3h", "1h"]` MUST be added to
  `AppSettings` so the user's last zoom preference is persisted between launches. Default
  `"24h"`.
- **FR-024**: The chart MUST support two top-level **modes**, toggled by a documented
  keybinding (suggested `h`):
  - **Live mode** (default): rolling 24 h window with `z` zoom (24 h / 3 h / 1 h),
    crosshair, pins, live tick at the right edge.
  - **History mode**: the existing multi-day timeframe picker (`today / 5d / 1mo / 3mo`)
    with no rolling window and no live-tick ingestion. The chart shows the full bar
    history at the chosen interval.
  In history mode, the live-mode bindings (`z`, `x`, pins, mouse-wheel zoom) MUST be
  suppressed; only the timeframe selection applies. Switching modes MUST NOT lose the
  user's last zoom or last timeframe choice — both persist independently in
  `AppSettings.chart_zoom` and `AppSettings.timeframe_index`.
- **FR-025**: The user's last selected **chart mode** MUST be persisted in
  `AppSettings.chart_mode: Literal["live","history"]` (default `"live"`) and restored on
  next launch.

#### Calendar panel — compact mode when Today is empty

- **FR-026**: When the macro-economic calendar's **Today** section has zero events, the
  `CalendarPanel` MUST collapse into a **single-row compact view** that shows the next
  N upcoming events inline (e.g.
  `No events today · next: Wed 14:30 FED CPI · Thu 13:45 ECB rate decision · Fri 08:00 RIKSBANK minutes`),
  rather than rendering the existing two-column Today/Upcoming layout with an empty
  Today column. The compact view MUST fit within the existing panel's single-row height
  (≤ 1 terminal row, truncating the trailing event with an ellipsis if width is
  exceeded).
- **FR-027**: When Today has ≥1 event, the panel MUST render the existing two-section
  layout (Today + Upcoming) unchanged.
- **FR-028**: The compact view MUST update reactively when the calendar snapshot
  changes — e.g. midnight rollover where the old "Today" becomes "Yesterday" and the new
  "Today" is empty MUST trigger a transition from the two-section layout to the compact
  row without restart.

### Key Entities

- **ChartViewState**: ephemeral per-chart state describing the current visible window.
  Fields: `zoom` (`"24h"` / `"3h"` / `"1h"`), `right_edge` (UTC datetime — the live edge),
  `crosshair_index` (int | None), `pinned_indices` (set[int]). Lives in the
  `PriceChart` widget, not persisted (zoom level persisted separately via FR-023).
- **StockQuote**: a polled equity quote. Fields: `ticker` (str, the raw user-supplied
  symbol), `display_name` (str, short label), `price` (float), `previous_close` (float),
  `change` and `change_percent` (derived), `intraday_closes` (tuple[float, ...] for the
  sparkline), `currency` (str — for tooltip / disambiguation between `LUG.TO` CAD and
  `LUG.ST` SEK), `time` (UTC datetime), `status` (`ok` / `stale` / `unavailable`).
- **StockTickerConfig**: user-editable list of tickers (`list[str]`) stored in
  `settings.json`. The service iterates this list on each refresh and emits one
  `StockQuote` per ticker.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From a cold start, both metals charts display ~24 h of bars filling the full
  panel width within **5 seconds** on a healthy network.
- **SC-002**: After 10 minutes of uptime the right edge of the chart shows the most recent
  tick (≤5 s old) and the leftmost x-tick label is exactly 24 h before the right edge.
- **SC-003**: Switching zoom level (24 h ↔ 3 h ↔ 1 h) re-renders the chart in **≤200 ms**
  without dropping in-flight ticks.
- **SC-004**: Hour ticks (`|`) and half-hour ticks (smaller `|`) are visually distinguishable
  by a quick glance — confirmed by user inspection on the user's terminal at the standard
  panel width.
- **SC-005**: Crosshair movement (arrow key) updates the price+time label within 50 ms per
  keystroke at all zoom levels.
- **SC-006**: Stock mini-tile row populates within **15 seconds** of cold start with at
  least N tiles (where N = `len(stock_tickers)` from settings).
- **SC-007**: Stock tile sparkline renders ≥10 intraday samples on a typical trading-day
  cold start.
- **SC-008**: Editing `stock_tickers` in `settings.json`, restarting the TUI, and seeing
  the tiles change to match — **0 crashes**, no need for any code edit.
- **SC-009**: All four background services (metals, calendar, FX, stocks) continue running
  during chart interactions (zoom, crosshair, pin) — verified by `last tick HH:MM:SS` in
  the status bar advancing while crosshair mode is active.

## Assumptions

- **Rolling 24 h replaces the existing "today-from-midnight" origin** for the metals
  charts in **live mode**. The existing `_x_origin = stockholm_midnight_utc()` becomes a
  rolling `now − 24 h` origin. The `today / 5d / 1mo / 3mo` timeframe picker is
  preserved but moves under a new **history mode** (FR-024), gated off the same chart
  widget by a mode toggle — not stacked alongside live-mode behaviour.
- **yfinance is sufficient for stock quotes**. The project already depends on yfinance for
  metals history and OMX. Reusing it for `LUG.TO / LUG.ST / LUMI.ST / LUNR` avoids a new
  upstream and respects the "free, no-API-key" rule.
- **Mouse-wheel scroll zoom is best-effort**. Textual exposes mouse-wheel events but the
  terminal must support them; we treat keyboard zoom as the canonical control and wheel as
  a bonus. The user accepts that some terminals will not give wheel events.
- **Sparkline data source = today's intraday closes**. We do not fetch a separate
  multi-day series for the mini-tiles; the sparkline is "since today's open at the
  exchange". For exchanges already closed (e.g. TSX during European evening), the sparkline
  shows that exchange's most recent session.
- **`stock_tickers` are raw yfinance symbols**. The user supplies symbols (`LUG.TO`,
  `LUMI.ST`, `LUNR`). The app does no auto-suffixing — what the user types is what is
  queried. This keeps the config explicit and lets the user point at any global market.
- **Pinned crosshair markers are NOT persisted across launches**. They are an in-session
  tool, not a saved analysis layer.
- **No new GUI framework**. Charts continue to use `textual-plotext`. Mini-tiles use the
  existing `Static`/`reactive` Textual primitives (mirroring `OmxStrip` / `FxTile`). No
  new chart library is introduced.
- **No persistence layer beyond `settings.json`**. Per the existing project rule, no
  database, no on-disk cache of quotes.
