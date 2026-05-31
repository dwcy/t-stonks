# Contract: PriceChart Widget (revised)

## Module
`goldsilver.widgets.chart`

## New / revised public surface

### Constructor (existing signature preserved)
```python
PriceChart(*, color, bucket_seconds=60.0)
```

### New methods
```python
def set_mode(self, mode: Literal["live", "history"]) -> None
def cycle_mode(self) -> None                           # live ↔ history
def set_zoom(self, zoom: Literal["24h", "3h", "1h"]) -> None     # live mode only
def cycle_zoom(self) -> None                           # 24h → 3h → 1h → 24h (live only)
def activate_crosshair(self) -> None                   # live mode only
def dismiss_crosshair(self) -> None
def move_crosshair(self, step: int) -> None            # negative = left, positive = right
def pin_current(self) -> None                          # toggle pin at crosshair index
def clear_pins(self) -> None
```

In **history mode** the `set_zoom` / `cycle_zoom` / crosshair / pin methods are no-ops
(the chart logs a debug message and returns). The history timeframe itself is selected
via the existing `PlotSettingsScreen` radio (driving `AppSettings.timeframe_index`), not
by the chart widget's own methods — to mirror the existing pre-feature architecture.

### Modified `seed()` signature
- `seed()` still accepts `bars` and `kind / show_sma / show_vwap / show_day_refs`.
- The `x_origin` parameter is **deprecated** — the new chart always uses a rolling 24 h
  window anchored to the rightmost bar's timestamp. The parameter is accepted but ignored
  (keeping the call site in `app.py` from breaking during the migration).

### Events (Textual messages, optional)
The widget MAY emit `PriceChart.ZoomChanged(zoom)` so the app can persist the new value
to `AppSettings.chart_zoom`. Implementation may instead expose a `zoom` reactive and let
the parent watch it.

## Internal state additions

```python
self._mode: Literal["live", "history"] = "live"
self._zoom: Literal["24h", "3h", "1h"] = "24h"
self._crosshair_active: bool = False
self._crosshair_index: int | None = None
self._pinned_indices: set[int] = set()
```

## Rendering rules

### x-axis range

**Live mode**:
- `right_edge_minutes = (bars[-1].time - origin).total_seconds() / 60`
- `window_minutes = {"24h": 1440, "3h": 180, "1h": 60}[self._zoom]`
- `xlim(right_edge_minutes - window_minutes, right_edge_minutes)`

Origin is the *first remaining bar*'s wall-clock-midnight in local TZ (kept constant for
the lifetime of the bar history, so ticks compute consistent offsets).

**History mode**:
- `xlim(0, (bars[-1].time - origin).total_seconds() / 60)` — show the entire seeded bar
  history. No rolling. No `add_point()`-driven slide; the chart is static between
  re-seeds. (Re-seeding happens when the user changes the history timeframe in
  `PlotSettingsScreen`.)

### Hour ticks (large)
Computed from `origin` + multiples of 60 min that fall inside the visible window. Rendered
via `plt.xticks(ticks, labels)` where each label is the local hour (e.g. `"14"`).

### Half-hour ticks (small)
At 24 h and 3 h zoom: ticks at `:30` offsets. At 1 h zoom: ticks at `:15`, `:30`, `:45`.
Rendered as a `plt.scatter` layer at `y = plt.ylim()[0]` with `marker="|"` and a dim
color. This is the second tick tier referenced in research.md Q5.

### Crosshair
When `_crosshair_active`:
- `idx = _crosshair_index or len(bars) - 1`
- Draw `plt.vline(xs[idx], color=(180, 180, 220))`
- Set the widget's `border_subtitle` to `f"  {bars[idx].time.astimezone():%H:%M}  {bars[idx].close:.2f}"`

### Pinned dots
For each `idx in _pinned_indices` that falls in the visible x-range, render a
`plt.scatter([xs[idx]], [closes[idx]], marker="●", color=(255, 213, 107))`.

## Key bindings
The app registers the following bindings; the chart widget exposes the methods called by
each:

| Key       | Action                                                       | Mode         |
|-----------|--------------------------------------------------------------|--------------|
| `h`       | `chart.cycle_mode()` (live ↔ history)                        | both         |
| `z`       | `chart.cycle_zoom()`                                         | live only    |
| `x`       | toggle `activate_crosshair` / `dismiss_crosshair`            | live only    |
| `←` / `→` | `move_crosshair(±1)` (only when crosshair active)            | live only    |
| `PgUp` / `PgDn` | move crosshair by 60 bars (~1 h at 1-min bucket)       | live only    |
| `Enter`   | `chart.pin_current()`                                        | live only    |
| `c`       | `chart.clear_pins()`                                         | live only    |
| `t`       | open history-mode timeframe picker (existing `p` already covers this; keep `t` as a shortcut) | history only |

Mouse-wheel-up / mouse-wheel-down → cycle zoom level (best-effort, live mode only).

In history mode, the live-mode keys are absorbed by the chart and ignored (not propagated
to other widgets) so a stray `z` doesn't surprise the user.

## Performance

- `_redraw()` cost per tick is unchanged from baseline (rolling-trim keeps `_bars` length
  bounded at ~1500 entries for 25 h at 1-min bucket).
- Crosshair update on arrow keypress: O(1) state update + one `_redraw()`, target ≤50 ms
  per keystroke (SC-005).

## Backwards compatibility

- Existing `seed()`, `add_point()`, `set_color()`, `apply_features()`, `apply_session_refs()`,
  `add_marker()`, `clear_markers()` signatures preserved.
- `apply_features()` no longer needs a `kind` parameter for the mini-tiles path — see the
  `StockTile` widget which uses a stripped-down render directly.
