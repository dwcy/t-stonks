# Phase 1 Data Model: Macro Calendar + FX + Brent

All models are Pydantic v2 (`BaseModel`, frozen, `ConfigDict(frozen=True)`), matching the
existing `Tick` / `Bar` style in `src/goldsilver/data/models.py`. They live next to the
existing models — either appended to `models.py` or split into `models_macro.py` if file
length warrants it. No new validation framework.

---

## CalendarSource (enum)

```text
FED       # Federal Reserve (FOMC + US releases via FRED)
ECB       # European Central Bank
RIKSBANK  # Sveriges Riksbank
```

Stored as `Literal["FED", "ECB", "RIKSBANK"]` on `CalendarEvent.source`. No subtypes for now
— if EconDB or another aggregator is added later it gets its own tag.

---

## EventImportance (enum)

```text
HIGH   # rate decision, NFP, CPI, FOMC press conference
MED    # PPI, retail sales, minutes, speeches by chair
LOW    # everything else returned by upstream
```

Optional on the model — `None` if upstream doesn't supply it.

---

## EventStatus (enum)

```text
SCHEDULED
RELEASED   # for releases with actual values back from upstream
CANCELLED  # only if upstream marks as cancelled
PASSED     # for visual styling: now > scheduled_time and no "actual" value
```

`PASSED` is computed in the rendering layer, not by upstream — never persisted.

---

## CalendarEvent

| Field | Type | Notes |
|---|---|---|
| `source` | `CalendarSource` | Required. |
| `title` | `str` | Required. Human-readable, English. Truncated to 60 chars in render but stored full. |
| `scheduled_time` | `datetime` (timezone-aware UTC) | Required. Internally always UTC; converted to Europe/Stockholm at render time. |
| `all_day` | `bool` | Default `False`. `True` for events like "Eurogroup meeting" with no time-of-day — render time as `--:--`. |
| `importance` | `EventImportance \| None` | Optional. |
| `forecast` | `str \| None` | Optional. Free text (e.g. `"0.3% m/m"`). |
| `previous` | `str \| None` | Optional. |
| `actual` | `str \| None` | Optional. Populated post-release. |
| `status` | `EventStatus` | Default `SCHEDULED`. |

### Validation rules

- `scheduled_time` must be tz-aware (Pydantic v2 `field_validator` rejects naive datetimes).
- If `all_day` is `True`, the time-of-day component MAY be `00:00` UTC — renderer must ignore
  it.
- `title` non-empty after `strip()`.

### Identity

Events have no upstream-provided ID. Within one snapshot, dedupe by tuple
`(source, scheduled_time, title.casefold())`.

---

## CalendarDay

A logical grouping used by the renderer; not persisted per se but constructed each render
pass.

| Field | Type | Notes |
|---|---|---|
| `date` | `date` (in Europe/Stockholm) | Required. |
| `bucket` | `Literal["yesterday", "today", "upcoming"]` | Required. |
| `events` | `list[CalendarEvent]` | Sorted ascending by `scheduled_time`. Empty list is valid (renders placeholder). |

### Bucket assignment rules

Given `today_stk = now().astimezone(STK).date()`:

- `bucket == "yesterday"` iff `date == today_stk - timedelta(days=1)`.
- `bucket == "today"` iff `date == today_stk`.
- `bucket == "upcoming"` iff `today_stk < date <= today_stk + timedelta(days=5)`.
- Events outside `[today_stk - 1, today_stk + 5]` are dropped from the snapshot — they are not
  used by the UI.

---

## CalendarSnapshot

| Field | Type | Notes |
|---|---|---|
| `days` | `list[CalendarDay]` | Length **7**: 1 yesterday, 1 today, 5 upcoming. Always all seven, in chronological order — empty days render the "no events" placeholder. |
| `fetched_at` | `datetime` (tz-aware UTC) | When the snapshot was assembled. |
| `status` | `Literal["ok", "stale", "unavailable"]` | `"ok"` after a successful fetch; `"stale"` when render falls back to a previous snapshot; `"unavailable"` when no snapshot has ever been fetched. |

### State transitions

```
unavailable --fetch_ok--> ok
ok          --fetch_fail--> stale (snapshot retained)
stale       --fetch_ok--> ok (new snapshot replaces)
```

The `CalendarService` owns the most-recent snapshot and emits one to subscribers after each
successful fetch.

---

## FxRate

| Field | Type | Notes |
|---|---|---|
| `pair` | `Literal["USDSEK", "CADSEK"]` | Required. |
| `rate` | `float` | Required. SEK per 1 unit of foreign currency (e.g. `10.4321` for USD/SEK). |
| `previous_close` | `float` | Required. Anchor for change/%. |
| `time` | `datetime` (tz-aware UTC) | Required. Upstream timestamp of the rate. |

### Derived properties (computed, not stored)

- `change = rate - previous_close`
- `change_percent = change / previous_close * 100.0` (guard divide-by-zero → `0.0`)

### Validation rules

- `rate > 1.0` and `previous_close > 1.0` — sanity guard for the Riksbank quote convention
  (see research.md R2). A value below 1.0 indicates a misparsed payload.
- `pair` ∈ exact set of supported pairs.

---

## CommodityQuote

Same shape as `FxRate` minus the currency-pair specifics. Reused for Brent.

| Field | Type | Notes |
|---|---|---|
| `symbol` | `Literal["BRENT"]` | Required. Extensible enum if more commodities added. |
| `price` | `float` | Required. USD/barrel for Brent. |
| `previous_close` | `float` | Required. |
| `time` | `datetime` (tz-aware UTC) | Required. |

### Derived

- `change = price - previous_close`
- `change_percent = change / previous_close * 100.0`

### Validation rules

- `price > 0.0`, `previous_close > 0.0`.

---

## Relationships

```
CalendarSnapshot
└── days: list[CalendarDay]              (length 7)
    └── events: list[CalendarEvent]      (zero or more)

FxRate            (one per pair: USDSEK, CADSEK)
CommodityQuote    (one per symbol: BRENT)
```

No shared parent. Each is emitted to widgets independently by its owning service:

- `CalendarService` → emits `CalendarSnapshot`
- `FxService` → emits per-pair `FxRate` on each refresh
- `CommodityService` → emits per-symbol `CommodityQuote` on each refresh

(All three may collapse into a single `MacroService` if the worker logic stays small. Decided
in implementation, not here.)

---

## Subscriber callback signatures

Matching the existing `MetalsService` pattern (`TickHandler`, `StatusHandler`):

```text
CalendarHandler = Callable[[CalendarSnapshot], Awaitable[None] | None]
FxHandler       = Callable[[FxRate], Awaitable[None] | None]
CommodityHandler= Callable[[CommodityQuote], Awaitable[None] | None]
```

The Textual app passes one handler per stream when constructing the service(s).
