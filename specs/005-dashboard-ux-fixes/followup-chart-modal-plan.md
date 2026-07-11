# Follow-up Plan: Chart Detail Modal — Weekly Strip + Full Feature Parity

Written 2026-07-11, on branch `005-dashboard-ux-fixes`, after live user testing of the
Story 9/10 chart detail modal surfaced three requests. Two smaller bugs from the same
testing session were fixed immediately (see "Already resolved" below) — this document
covers the two larger items that need a dedicated implementation pass.

**Status: implemented 2026-07-11.** Both parts landed as described below, plus one bug
found while wiring up the new key bindings: `StockChartScreen` had no `AUTO_FOCUS`
override, so Textual's `App.AUTO_FOCUS = "*"` default auto-focused the "Close" button
on open, which then swallowed the new `enter` (pin) binding as a button press instead
of letting it bubble to the screen. Fixed by setting `AUTO_FOCUS = ""` on the screen.
Verified live via a Pilot smoke test: weekly strip groups correctly (`w19[...] w20[...]`),
chart seeds with SMA/VWAP/day-refs all on and `mode="history"`, and `h`/`x`/`enter`/`c`
all mutate real `PriceChart` state. One known, accepted quirk: `z` (zoom) and `h` (mode)
are wired for parity per the user's explicit "don't cherry-pick" direction, but zooming
and switching to `mode="live"` are functionally no-ops/visually degenerate for daily
bars (zoom windows are in minutes; live mode assumes a live tick stream) — this is a
structural property of the shared `PriceChart` widget, not something introduced here.

## Context

The chart detail modal (`StockChartScreen`, `src/marketcore/widgets/stock_chart_screen.py`)
opens when a user clicks a stock tile's mini sparkline. It currently:

- Seeds a `PriceChart` with `color="white"` and no zoom/mode/crosshair/VWAP/day-ref
  wiring — just `.seed(bars, kind="line")` with defaults (SMA on, everything else off).
- Renders a flat, un-grouped 40-day up/down strip via `DailyChangeStrip`.
- Uses `PriceChart`'s own `DEFAULT_CSS` (`height: 16`) unmodified — the same fixed
  height as the tiny always-visible gold/silver panel chart, despite the modal dialog
  itself being `width: 100`.

User's explicit direction when asked how far to take feature parity: **reuse the same
`PriceChart` component fully, the way `MetalPanel` already does — don't cherry-pick
which controls "make sense" for daily bars, just wire it up the same way.**

## Part A — Weekly-grouped 40-day strip

**File**: `src/marketcore/widgets/daily_change_strip.py`

**Current**: `DailyChangeStrip._build_text()` renders all `DailyChange` entries as one
flat continuous row (`▲+1.2%  ▼-0.8%  ...`).

**Wanted**: grouped by ISO week number, like `w32[▲+1.2% ▼-0.8% ...] w33[...]`.

**Plan**:

- `compute_daily_changes()` stays unchanged (still returns a flat, chronologically
  sorted `list[DailyChange]`) — its existing tests in `tests/marketcore/test_stock_history.py`
  must keep passing untouched. Grouping happens only in the render step.
- In `_build_text()`, group consecutive entries by `change.date.isocalendar().week`
  using `itertools.groupby` (safe here specifically *because* the input is already
  chronologically sorted — `groupby` only merges consecutive equal keys, it does not
  bucket non-adjacent same-key items).

```python
from itertools import groupby

def _build_text(changes: list[DailyChange]) -> Text:
    if not changes:
        return Text("No daily history available.", style=FLAT_COLOR)
    text = Text()
    for week_num, group in groupby(changes, key=lambda c: c.date.isocalendar().week):
        text.append(f"w{week_num:02d}[", style=MUTED_COLOR)
        for i, change in enumerate(group):
            if i > 0:
                text.append(" ")
            # existing arrow/color/pct logic per entry, unchanged
            ...
        text.append("]\n", style=MUTED_COLOR)
    return text
```

**Tests**: extend `tests/marketcore/test_stock_chart_screen.py` (or add a case to
`test_stock_history.py`) asserting `w<NN>[` brackets appear with the correct ISO week
numbers for a `Bar` list known to span 2+ calendar weeks.

## Part B — Larger chart + full feature parity with gold/silver

**Files**: `src/marketcore/widgets/stock_chart_screen.py`,
`src/goldsilver/styles/app.tcss`, `src/quantum/styles/app.tcss`,
`src/goldsilver/app.py`, `src/quantum/app.py`

**Reference pattern** — exactly how `MetalPanel` + `app.py` already wire this same
`PriceChart` widget for gold/silver, to mirror:

- `MetalPanel` has thin wrapper methods — `set_chart_zoom`, `cycle_chart_zoom`,
  `set_chart_mode`, `cycle_chart_mode`, `toggle_crosshair`, `move_crosshair`,
  `pin_current`, `clear_pins` — each just calling the matching `PriceChart` method
  (`src/goldsilver/widgets/metal_panel.py`).
- `GoldSilverApp.BINDINGS` maps `z` → `action_cycle_zoom`, `h` → `action_cycle_chart_mode`,
  `x` → `action_toggle_crosshair`, `left`/`right` → crosshair move,
  `pageup`/`pagedown` → crosshair page move, `enter` → `action_pin_current`,
  `c` → `action_clear_pins` — all operating on `_all_metal_panels()` (`src/goldsilver/app.py`).
- `apply_chart_features(*, kind, show_sma, show_vwap, show_day_refs)` is driven by the
  `PlotSettings` dataclass (user-toggleable in the settings screen).

**Plan**:

1. Add the same binding set to `StockChartScreen.BINDINGS` (currently just `escape`):
   `z`, `h`, `x`, `left`, `right`, `pageup`, `pagedown`, `enter`, `c`. Add matching
   `action_*` methods on `StockChartScreen` that call
   `self.query_one(PriceChart).cycle_zoom()` etc. — same one-line-wrapper shape
   `MetalPanel` already uses, just at the screen level instead of the panel level.
2. Seed with the full feature set on by default: `show_sma=True, show_vwap=True`.
   **Open question to resolve during implementation**: `show_day_refs` needs
   `apply_session_refs(prev_close, day_high, day_low)`, which gold/silver gets from
   its live tick stream — `fetch_daily_history()`'s `Bar` list has no equivalent
   per-bar prev-close/session-high/low concept for an arbitrary stock. Either (a)
   compute a synthetic "prev close" from the bars list itself (the second-to-last
   bar's close) before calling `.seed()`, or (b) leave `show_day_refs=False` for this
   modal specifically since there's no live session to reference. Given the user's
   "just reuse the component" direction, prefer (a) if it's a small addition;
   confirm with the user if it's not obviously correct once attempted.
3. **Accent color**: replace the hardcoded `PriceChart(color="white")` with a real
   color. Quantum already has per-ticker accent colors in
   `src/quantum/data/presets.py` — thread that through for quantum tickers. Goldsilver
   stock tiles have no per-ticker accent concept today; default to the modal's own
   border accent (`#8ab4ff`) or a neutral bright color there.
4. **Sizing**: `PriceChart`'s `DEFAULT_CSS` is `height: 16` (tuned for the small
   always-visible panel). Override for the modal specifically in both
   `goldsilver/styles/app.tcss` and `quantum/styles/app.tcss`:
   ```css
   #stock-chart-dialog PriceChart {
       height: 30;
   }
   ```
   Tune the exact number by actually looking at it — `30` is a starting guess given
   the dialog is already `width: 100`. `#stock-chart-dialog` itself stays `height: auto`
   so it grows to fit.
5. **Fetch-failure resilience** (found during this session's investigation, not
   originally requested but worth doing while in this code): `fetch_daily_history()`
   catches all exceptions and returns `[]` on any transient yfinance failure
   (rate-limit, network blip) — separate from the NaN-bar bug already fixed. An empty
   bars list currently renders a silently blank chart (`PriceChart._redraw()` no-ops
   below 2 bars) with zero user-facing indication anything failed. Add a clear
   "Couldn't load chart data" message in `StockChartScreen` when `bars` is empty, with
   a retry action (e.g. `r` binding that re-runs the fetch and re-seeds), rather than
   leaving the modal looking broken.

## Verification

- Live smoke test opening the modal for a real ticker (same pattern used throughout
  005's implementation: construct the app, click `_StockSpark`, wait for
  `StockChartScreen` to mount, inspect `chart._bars`, `chart.zoom`, `chart.mode`).
- Confirm the new key bindings actually mutate `PriceChart` state when the modal has
  focus (zoom cycles, crosshair toggles/moves, mode cycles).
- Confirm the weekly strip renders correct week numbers against a `Bar` list with a
  known date range spanning multiple ISO weeks.
- Confirm the empty-bars retry path actually re-fetches and re-seeds on `r`.

## Already resolved this session (context, not part of this follow-up)

- **NaN-bar chart-blanking bug**: `fetch_daily_history()` didn't filter yfinance's
  still-forming "today" row (NaN OHLC), which broke `PriceChart`'s y-axis range
  calculation and left the whole chart blank. Fixed in commit `969a5a2` — the function
  now skips any row with a non-finite OHLC/volume value, matching the NaN-filter
  pattern already used elsewhere in this codebase (`commodity_service.py`).
- **PressTV timestamps**: live-verified PressTV's RSS feed carries no per-item
  timestamp anywhere (no `<pubDate>`, no `<dc:date>` — only a channel-level
  `<lastBuildDate>`), so even with Story 1's honest `~` approximate-marking, values
  always cluster within minutes of fetch time. Removed as a news source entirely in
  commit `d2fcccd` per the user's explicit choice, rather than keep shipping
  timestamps that structurally can't be accurate.
