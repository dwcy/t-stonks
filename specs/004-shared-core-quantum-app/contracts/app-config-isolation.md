# Contract: Per-App Config Isolation & Feed Injection

Two parameterizations make one shared layer serve many apps without collision.

## C1 — Config base takes an app name

`marketcore/paths.py`:
```python
def config_base(app_name: str) -> Path:
    # Windows: %APPDATA%\<app_name>   (fallback ~/AppData/Roaming/<app_name>)
    # POSIX:   $XDG_CONFIG_HOME/<app_name>  (fallback ~/.config/<app_name>)

def settings_path(app_name: str) -> Path:  # config_base(app_name)/settings.json
def trades_path(app_name: str) -> Path:    # config_base(app_name)/trades.json
def reports_dir(app_name: str) -> Path:    # config_base(app_name)/reports/
```

### Guarantees
- `goldsilver` calls these with `"goldsilver"` → resolves to the **exact same path** as
  before this feature (`%APPDATA%/goldsilver/settings.json`). No migration of existing
  user files (FR-3).
- `quantum` calls them with `"quantum"` → fully separate directory (FR-8).
- `app_name` is validated as a non-empty slug `[a-z0-9_-]+`; invalid names raise.

### Acceptance
- `settings_path("goldsilver")` equals the pre-refactor `settings_path()` output on the
  same OS/env (regression test pins this).
- `settings_path("quantum") != settings_path("goldsilver")`.

## C2 — News feeds are injected

`marketcore/services/news_service.py`:
```python
class NewsService(PollingService):
    def __init__(self, feeds: Sequence[tuple[NewsSource, str]],
                 handler=None, stale_handler=None, *,
                 refresh_interval_s=NEWS_REFRESH_INTERVAL_S,
                 max_items=200, per_source_cap=5) -> None: ...
```

### Guarantees
- No module-global `NEWS_FEEDS` is read inside `marketcore`. The feed list is always a
  constructor argument.
- `goldsilver` passes its existing feed list (relocated to `goldsilver/data/news_feeds.py`);
  the resulting news content is identical to pre-refactor.
- `quantum` passes `QUANTUM_NEWS_FEEDS` from `quantum/data/news_feeds.py`.

### Acceptance
- Constructing `NewsService(feeds=[...])` with two different lists yields two services
  that fetch their respective feeds (unit test with a stub HTTP client).
- `goldsilver` news output unchanged (same feeds in, same `NewsItem`s out).

## C3 — Import direction (enforced)

App → `marketcore` only. `marketcore` → (stdlib + third-party) only. A test asserts no
`goldsilver`/`quantum` import appears under `src/marketcore/`.
