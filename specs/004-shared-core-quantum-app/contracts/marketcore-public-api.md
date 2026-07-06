# Contract: `marketcore` Public Import Surface

`marketcore` is the lower layer. This contract defines what it guarantees to consumers
(`goldsilver`, `quantum`, future apps) and the one rule it must never break.

## Invariant (non-negotiable)

**`marketcore` imports nothing from any app package.** No `import goldsilver`, no
`import quantum`, anywhere under `src/marketcore/`. Verified by a test that greps the
package and by import-time success when no app is installed.

## Stable exports

Consumers import from these module paths (re-exported via `marketcore/__init__.py`
where convenient):

### Models
```python
from marketcore.models import Tick, Bar
from marketcore.models_macro import (
    StockQuote, NewsItem, NewsSource, Signal,
    FxRate, CommodityQuote,  # … existing macro models
)
```

### Services
```python
from marketcore.services.base import PollingService
from marketcore.services.stock_service import StockService
from marketcore.services.news_service import NewsService          # feeds injected
from marketcore.services.fx_service import FxService
from marketcore.services.commodity_service import CommodityService
# … futures / yields / calendar / insider / congress / stocktwits as moved
```

### Service contract (`PollingService`)
```python
class PollingService:
    def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def refresh_now(self) -> None: ...
    # subclasses implement:
    async def _refresh_once(self, client) -> None: ...
```
- `start()` is idempotent (no double task).
- `stop()` cancels and awaits the loop; safe to call when never started.
- A failed refresh emits via `stale_handler`, never crashes the loop.

### Paths
```python
from marketcore.paths import config_base, settings_path, trades_path, reports_dir
# each takes app_name: str (filesystem-safe slug)
```

### Widgets
```python
from marketcore.widgets.chart import PriceChart
from marketcore.widgets.stock_tile import StockTile
from marketcore.widgets.fx_tile import FxTile
from marketcore.widgets.commodity_tile import CommodityTile
from marketcore.widgets.ratio_tile import RatioTile   # thresholds via constructor
```

### Reports (available to apps that opt in)
```python
from marketcore.reports.claude_runner import find_claude, run_claude
from marketcore.reports.report_service import ReportService
from marketcore.reports.html_writer import write_report, write_index
```

## Backward-compatibility facades (in `goldsilver`)

To keep the `goldsilver` diff small, these old paths continue to work by re-exporting:
- `goldsilver/data/models.py` → re-exports `Tick`, `Bar` from `marketcore.models`;
  still defines `GOLD`, `SILVER`, `SYMBOLS`.
- `goldsilver/data/http.py` → re-exports `make_client`.
- `goldsilver/data/session.py` → `stockholm_*` wrappers calling the tz-parameterized
  `marketcore.session` helpers with `Europe/Stockholm`.

## Acceptance checks

- `python -c "import marketcore"` succeeds with no app packages on the path.
- `grep -r "import goldsilver\|import quantum" src/marketcore` returns nothing.
- All listed exports resolve (an import smoke test imports every symbol above).
