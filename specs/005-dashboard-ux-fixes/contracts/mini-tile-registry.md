# Contract: Mini-Tile Registry Extension

Governs how Stories 7 and 8 plug new tiles into `goldsilver`'s existing mini-tile
strip without changing its dispatch mechanism.

## Existing contract (unchanged)

`goldsilver/data/settings.py::ALLOWED_MINI_TILES` is the source of truth for which
tile keys a user may select into `AppSettings.mini_tiles`. `goldsilver/app.py`'s
`_macro_strip_widgets()` turns each selected key into a widget instance via an
if/elif chain keyed against frozensets (`_FX_PAIR_IDS`, `_COMMODITY_IDS`, plus single
constants like `_RATIO_ID`, `_REAL_YIELD_ID`). This method runs both at initial build
and on settings change (`_apply_mini_tiles()`), which clears and remounts the strip.

## Extension for this feature

New keys added to `ALLOWED_MINI_TILES`:

| Key | Story | Widget | Backing service |
|---|---|---|---|
| `FEDRATE` | 7 | `RateTile(source="fed")` | `RateService` (FRED `DFF`) |
| `RIKSRATE` | 7 | `RateTile(source="riksbank")` | `RateService` (Riksbank REST) |
| `DAX` | 8 | `IndexTile("DAX")` | `IndexService("DAX", "^GDAXI", tz="Europe/Berlin")` |
| `CAC40` | 8 | `IndexTile("CAC40")` | `IndexService("CAC40", "^FCHI", tz="Europe/Paris")` |
| `FTSE100` | 8 | `IndexTile("FTSE100")` | `IndexService("FTSE100", "^FTSE", tz="Europe/London")` |
| `NIKKEI225` | 8 | `IndexTile("NIKKEI225")` | `IndexService("NIKKEI225", "^N225", tz="Asia/Tokyo")` |

Each new key is added to a new frozenset (`_RATE_IDS`, `_INDEX_IDS`) so the existing
if/elif chain in `_macro_strip_widgets()` grows by two branches, not six — following
the same pattern already used for `_FX_PAIR_IDS`/`_COMMODITY_IDS`.

## Interface each new service must satisfy

Matches the shape `RealYieldService` already establishes (no new base class required,
but new services should follow it for consistency):

```python
class <X>Service:
    def __init__(self, *, handler: Callable[[<Point>], None]) -> None: ...
    def start(self) -> None: ...           # begins the refresh loop
    async def stop(self) -> None: ...       # cancels the loop, awaited at shutdown
    async def refresh_now(self) -> None: ...  # manual refresh, used by refresh keybindings
```

`RateService` and `IndexService` both call `handler(point)` on each successful
refresh; `app.py` wires the handler exactly like `_on_real_yield` wires
`RealYieldTile.apply_point()` today.

## Tile widget contract

```python
class RateTile(Static):
    def apply_point(self, point: RatePoint) -> None: ...

class IndexTile(Static):
    def apply_point(self, point: IndexPoint) -> None: ...
```

Both follow `CommodityTile`/`RealYieldTile`'s existing shape: a reactive point field,
`watch_*` triggers `_redraw()`, single-line `Text.assemble(...)` render with an
up/down/flat arrow. `IndexTile` additionally renders a "closed" marker when
`point.session_open is False` (FR-033).

## Quantum app — explicitly out of scope

`quantum/app.py` has no mini-tile concept (fixed ETF/stock lists via `compose()`, no
`ALLOWED_MINI_TILES` equivalent). Stories 7 and 8 only apply to `goldsilver`; this is
consistent with the spec, which frames both stories around gold/silver dashboard
context (rate/index correlation with metals), not quantum stocks.
