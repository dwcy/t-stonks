# Phase 0 Research: Shared `marketcore` Layer + `quantum` App

## R1 — Monorepo packaging: one pyproject, multiple packages + scripts

**Decision**: Keep a single `pyproject.toml` at the repo root. Place three packages
under `src/` (`marketcore`, `goldsilver`, `quantum`). Register two console scripts:

```toml
[project.scripts]
goldsilver = "goldsilver:main"
quantum    = "quantum:main"
```

**Rationale**: The `uv_build` backend (already in use) auto-discovers every top-level
package directory under `src/`. One `pyproject.toml` means one `uv.lock`, one `uv sync`,
and one environment in which `marketcore` is importable by both apps with no separate
build/publish step. `uv run goldsilver` and `uv run quantum` resolve to the two scripts.

**Alternatives considered**:
- *Separate distributions / workspace members*: `uv` workspaces would let `marketcore`
  be its own package. Rejected as over-engineering for a personal multi-app repo — adds
  multiple `pyproject.toml` files and path-dependency wiring with no benefit here.
- *Keep everything in `goldsilver` and have `quantum` import `goldsilver.*`*: rejected —
  forces the quantum app to depend on a metal-branded package and never establishes the
  clean lower layer the user asked for.

## R2 — Extraction mechanics: relocate-and-reimport, guarded by tests

**Decision**: Move modules wholesale into `marketcore`, then fix import paths in
`goldsilver`. Where a name was widely imported, leave a thin facade in the old location
that re-exports from `marketcore` (e.g. `goldsilver/data/models.py` re-exports `Tick`,
`Bar` and additionally defines `GOLD`/`SILVER`). Run `uv run pytest` after each move.

**Rationale**: The exploration confirmed the services are already callback-based and
symbol-agnostic, so the risk is import breakage, not logic change. Facades keep the diff
in app code minimal and reviewable. The existing test suite is the safety net.

**Alternatives considered**:
- *Rewrite services against a new base class*: rejected — unnecessary churn and risk on
  working code; violates the user's "reuse where possible" intent.

## R3 — The one true abstraction to extract: `PollingService`

**Decision**: Extract a small async base class `PollingService` capturing the repeated
loop (`start` / `stop` / `refresh_now` / `_run` with `asyncio.Event` stop + interval
wait + stale emission). Concrete services (`StockService`, `NewsService`/`_FeedService`,
`FxService`, `MetalsService`, …) subclass it and implement `_refresh_once`.

**Rationale**: Every service in `data/` re-implements the identical loop skeleton (seen
in `stock_service.py:40-59`, `news_service.py`, `service.py`). One base removes the
duplication and gives `quantum`'s future bespoke services a one-method contract. The
existing `_FeedService` in `news_service.py:152` is already this shape and folds in
cleanly.

**Alternatives considered**:
- *Leave each service standalone*: rejected — the duplication is the strongest signal in
  the codebase that a base belongs in the shared layer.

## R4 — News feeds must be injectable, not a module constant

**Decision**: `NewsService.__init__` gains a `feeds: Sequence[tuple[NewsSource, str]]`
parameter. `goldsilver` passes its current `NEWS_FEEDS` (from a new
`goldsilver/data/news_feeds.py`); `quantum` passes a quantum-computing feed list.

**Rationale**: Today `news_service.py:236` reads the module-global `NEWS_FEEDS`
directly, so two apps cannot have different feeds without forking the file. Injection is
the minimal change that unblocks `quantum`'s news requirement (FR-5, FR-7).

**Quantum news feeds (default set)** — Google News RSS topic queries + vendor feeds,
matching the existing pattern (`news.google.com/rss/search?q=...`):
- `when:24h "quantum computing"` (general)
- `when:24h (IonQ OR Rigetti OR "quantum computing" OR QTUM)` (market-flavoured)
- The Quantum Insider site feed (`site:thequantuminsider.com`)
- Reuters/Bloomberg tech filtered to quantum via the query.

Exact URLs are finalized in `data-model.md`; all use feeds already reachable without
keys, consistent with the no-API-key constraint.

## R5 — Per-app config isolation

**Decision**: Promote `_config_base()` + `settings_path()`/`trades_path()`
(`settings.py:506-517`) into `marketcore/paths.py` as `config_base(app_name)`,
`settings_path(app_name)`, `trades_path(app_name)`, `reports_dir(app_name)`.
`goldsilver` calls them with `"goldsilver"`; `quantum` with `"quantum"`.

**Rationale**: The directory segment is the only thing standing between two apps sharing
or clobbering each other's settings. Parameterizing the app-name segment gives clean
isolation (FR-4, FR-8) and preserves `goldsilver`'s existing path verbatim
(`%APPDATA%/goldsilver/...`), so no user migration is needed (FR-3).

**Alternatives considered**:
- *Single shared config with per-app sections*: rejected — couples app schemas and
  risks one app's settings model breaking another.

## R6 — Quantum instruments: ETFs + pure-play stocks

**Decision**: Track all three via the reused stock pipeline (yfinance through
`StockService`), differing only in presentation:
- **ETF headline tiles**: `QTUM` (Defiance Quantum ETF) and a second quantum-themed ETF
  (e.g. `QTUM`-peer); rendered as the prominent panels (analogous to gold/silver's two
  headline panels).
- **Pure-play stock grid**: `IONQ`, `RGTI`, `QUBT`, `QBTS`, `ARQQ` (extensible via
  presets), rendered with `StockTile` (live quote + change% + sparkline).

**Rationale**: ETFs and equities are both ordinary yfinance tickers, so one
`StockService` instance covers them; the only difference is which widget renders which
ticker. This maximizes reuse (FR-7) and needs no bespoke quantum data service for the
first cut. Defaults ship as editable presets so the watchlist is not hardcoded.

**Validation note**: ticker symbols are treated as configurable defaults, not
guarantees of current listing; the app degrades gracefully (stale handler) if a symbol
is delisted or renamed — same behaviour as `goldsilver`'s stock panel today.

**Alternatives considered**:
- *Dedicated `QuantumService` hitting a quantum-specific endpoint*: rejected — no such
  free near-real-time endpoint exists for these names, and yfinance already serves them.

## R7 — Report engine reuse is optional for the first quantum cut

**Decision**: Move the Claude report engine into `marketcore.reports` (it is already
generic apart from the prompt builder and locale phases). The first `quantum` release
wires the live dashboard (ETF + stocks + news) and may omit the AI report screen; the
engine is available for a later `quantum` prompt builder without further extraction.

**Rationale**: Keeps the quantum scope focused on the user's stated three feeds while
ensuring the report engine lands in the shared layer so a quantum prompt builder is a
drop-in later. Avoids gold-specific prompt text leaking into the quantum app.

## Resolved unknowns

| Unknown | Resolution |
|---------|-----------|
| Core package name | `marketcore` (user decision) |
| Quantum scope | ETF tiles + pure-play stock panel + news feed (user decision) |
| Extraction depth | Foundation extraction (user decision) |
| How apps coexist in one repo | One `pyproject.toml`, three `src/` packages, two scripts (R1) |
| Config collision between apps | `app_name`-parameterized config base (R5) |
| Differing news feeds per app | Injected feed list (R4) |
| Quantum data source | yfinance via reused `StockService`; Google-News-RSS quantum feeds (R6, R4) |
