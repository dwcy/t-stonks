# TUI Widget Contracts

What new widgets exist, what they own, what reactive attributes they expose, what they don't.

---

## 1. `CalendarPanel` (new widget)

**File**: `src/goldsilver/widgets/calendar_panel.py`

**Subclasses**: `textual.widget.Widget`

**Role**: renders the three-section calendar (Yesterday / Today / Upcoming 5 days).

**Reactive attributes**:

| Attribute | Type | Default | Notes |
|---|---|---|---|
| `snapshot` | `CalendarSnapshot \| None` | `None` | Set by app on each `CalendarHandler` callback. Triggers re-render. |
| `now_stk` | `datetime` | `datetime.now(STK)` | Bumped once per minute by an internal `set_interval` so the "passed event" dimming updates without waiting for a fetch. |

**Inputs**:

- `apply_snapshot(snapshot: CalendarSnapshot)` — sets `self.snapshot`. Called by app from
  `CalendarHandler`.

**Outputs / events**:

- None. Widget is read-only; refresh is via keybinding handled by the app.

**Render contract**:

```
┌── Macro Calendar ────────── fetched 12:07 ──┐
│ Yesterday  Wed 27 May                       │
│   14:30  FED   CPI                          │
│                                             │
│ Today      Thu 28 May                       │
│   14:15  ECB   Lagarde press conference     │
│   16:00  RIKSBANK  Rate decision            │
│                                             │
│ Upcoming                                    │
│ Fri 29 May                                  │
│   14:30  FED   NFP                          │
│ Sat 30 May                                  │
│   (no scheduled events)                     │
│ ...                                         │
└─────────────────────────────────────────────┘
```

**Style classes**:

- `.calendar-yesterday` and `.calendar-upcoming` → muted gray (existing `#7a7a8a`).
- `.calendar-today` → bright `#e0e0e8` (matches `Screen.color`).
- `.calendar-event-passed` → strikethrough or dim, applied when
  `now_stk > event.scheduled_time` and event is in today's bucket.
- All defined in `src/goldsilver/styles/app.tcss`.

**Failure mode rendering**:

- `snapshot is None` → render `loading…` placeholder.
- `snapshot.status == "stale"` → render normally + a `stale since HH:MM` line in dim red.
- `snapshot.status == "unavailable"` → render `calendar unavailable — retrying` in dim red.

---

## 2. `FxTile` (new widget)

**File**: `src/goldsilver/widgets/fx_tile.py`

**Subclasses**: `textual.widget.Widget`

**Role**: renders a single FX pair (USD/SEK or CAD/SEK).

**Reactive attributes**:

| Attribute | Type | Default | Notes |
|---|---|---|---|
| `rate` | `FxRate \| None` | `None` | Last known. |
| `stale_since` | `datetime \| None` | `None` | Set by app when service reports stale. |

**Inputs**:

- `apply_rate(rate: FxRate)` — store and re-render.
- `mark_stale(since: datetime)` — set `stale_since`, retain `rate`.

**Render contract** (one tile per pair):

```
USD/SEK  10.4321  ▲ +0.42% (+0.0435)
```

- Direction arrow: `▲` (up), `▼` (down), `▬` (flat — abs change < 0.0001).
- Color: green for up, red for down, dim for flat — matches metals panel convention.
- Stale: appends `· stale since HH:MM` in dim red at end of line.

---

## 3. `CommodityTile` (new widget)

**File**: `src/goldsilver/widgets/commodity_tile.py`

**Subclasses**: `textual.widget.Widget`

**Role**: renders a single non-charted commodity quote (Brent for MVP).

**Reactive attributes**: same shape as `FxTile` (`quote: CommodityQuote | None`,
`stale_since`).

**Render contract**:

```
BRENT  68.46  ▼ -1.54% (-1.07)
```

Identical formatting to `FxTile`, swapping `pair` → `symbol`.

---

## 4. App layout changes

**File**: `src/goldsilver/app.py`

The existing `Horizontal#metals` row remains unchanged. A new compact strip is added below
the metals row and above the status bar:

```
┌─────────────────────────────────────────────────────────────────────┐
│ Header                                                              │
├──────────────────────────────┬──────────────────────────────────────┤
│ GOLD panel                   │ SILVER panel                         │
│ (existing chart + stats)     │ (existing chart + stats)             │
├──────────────────────────────┴──────────────────────────────────────┤
│ FX strip:  USD/SEK ...    CAD/SEK ...    BRENT ...    [calendar →]  │
├─────────────────────────────────────────────────────────────────────┤
│ Calendar panel                                                      │
│ Yesterday / Today / Upcoming                                        │
├─────────────────────────────────────────────────────────────────────┤
│ Status bar  ·  Footer                                               │
└─────────────────────────────────────────────────────────────────────┘
```

- FX strip is a thin `Horizontal` containing the two `FxTile`s and one `CommodityTile`, height
  1 with padding 0 1, dim background like the status bar.
- Calendar panel below it expands to fill remaining vertical space, with internal vertical
  scrolling if events overflow.

---

## 5. Keybindings (additions)

| Key | Action | Description |
|---|---|---|
| `c` | `refresh_calendar` | Triggers an immediate `CalendarService` fetch. |
| `f` | `refresh_fx`        | Triggers an immediate FX + Brent fetch. |

Existing `q`, `t`, `r` are unchanged.

---

## 6. Service-to-widget wiring

```
MetalsService          (existing)  ──► MetalPanel × 2          (existing)

CalendarService        (new)       ──► CalendarPanel           (new)
FxService              (new)       ──► FxTile × 2              (new)
CommodityService       (new)       ──► CommodityTile × 1       (new)
```

The app holds one reference per service, starts/stops them in `on_mount` / `on_unmount`, and
passes per-widget handlers exactly like `MetalsService`'s `tick_handler` / `status_handler`
pattern.

If during implementation the three new services have near-identical loop/backoff logic, they
MAY collapse into a single `MacroService` exposing three handler slots. The widget layer
above does not change either way.

---

## 7. Backwards compatibility

- All existing widgets (`MetalPanel`, header, footer, status bar) are unmodified.
- All existing keybindings (`q`, `t`, `r`) keep their current semantics.
- All existing CSS classes (`.-gold`, `.-silver`, `#status-bar`) are unmodified.
- The TUI continues to run with the new features fully disabled if `GOLDSILVER_DISABLE_MACRO=1`
  env var is set (escape hatch for debugging only — not exposed in CLI / docs).
