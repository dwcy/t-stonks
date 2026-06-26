---

description: "Task list for Shared marketcore Layer + quantum App"
---

# Tasks: Shared `marketcore` Layer + `quantum` App

**Input**: Design documents from `specs/004-shared-core-quantum-app/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: INCLUDED — spec FR-9 explicitly requires tests (regression for `goldsilver`,
new tests for the parameterized `marketcore` surface, and a `quantum` smoke test).

**Organization**: Tasks are grouped by user story. The shared `marketcore` extraction is
the Foundational phase (both apps depend on it).

## Implementation Status (2026-06-27)

**Delivered & green (207 tests pass; `uv run goldsilver` unchanged, `uv run quantum` works):**
- Phase 1 Setup — complete.
- Phase 2 Foundational — the leaves + what quantum needs are extracted into `marketcore`:
  `http`, `fsutil`, `models` (Tick/Bar), `models_macro`, `session` (tz-parameterized),
  `paths` (app-name), `services/base.PollingService`, `services/stock_service`,
  `services/news_service` (feed-injected), `widgets/{chart,stock_tile,format}`.
  goldsilver re-points to all of these via facades.
- Phase 3 US1 — goldsilver verified unchanged (settings path preserved; full suite green).
- Phase 4 US2 — `quantum` app complete (presets, feeds, settings, app, console script, smoke test).
- Phase 5 US3 — import-direction guard + public-API test + docs.

**Deferred (not required by quantum; left in `goldsilver`, still importing the shared
leaves from `marketcore`):** moving the remaining generic services
(`fx/commodity/futures/calendar/congress/insider/yields/omx/history`), the
strategy/backtest/trade engine, and the Claude report engine into `marketcore`
(T013–T016), plus rebinding `MetalsService` onto `PollingService` (T021). These are
mechanical follow-ups; the report engine additionally needs metal-decoupling
(METAL_LABELS / Swedish phases) before it can move. Tracked here, not yet done.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 = goldsilver-unchanged, US2 = quantum app, US3 = third-app extensibility

## Path Conventions

Multi-package monorepo under `src/`: `src/marketcore/` (shared), `src/goldsilver/` (app),
`src/quantum/` (new app). Tests under `tests/`. Single `pyproject.toml` at repo root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create the new package skeletons and test scaffolding.

- [x] T001 Create `src/marketcore/` package skeleton with `__init__.py` and subpackages `services/`, `widgets/` (each with `__init__.py` and a one-line module docstring)
- [x] T002 [P] Create `tests/marketcore/` and `tests/quantum/` directories
- [x] T003 [P] Add import-direction guard test `tests/marketcore/test_import_direction.py` asserting no `goldsilver`/`quantum` import appears under `src/marketcore/`

**Checkpoint**: Package and test skeletons exist; `python -c "import marketcore"` succeeds.

---

## Phase 2: Foundational (Blocking Prerequisites — the shared extraction)

**Purpose**: Move the symbol-agnostic foundation into `marketcore`, parameterizing the
three things that block multi-app use (config app-name, news feeds, `PollingService`).
Each move re-points `goldsilver` import sites so the suite stays green.

**⚠️ CRITICAL**: No user story can be completed until this phase is done. `goldsilver`
must remain green after each move (run `uv run pytest` as the gate).

- [x] T004 Move `make_client` → `src/marketcore/http.py`; `src/goldsilver/data/http.py` is now a facade
- [x] T005 Move `Tick`, `Bar` → `src/marketcore/models.py`; `GOLD`/`SILVER`/`SYMBOLS` kept in `src/goldsilver/data/models.py` re-exporting `Tick`/`Bar`
- [x] T006 Move all macro models → `src/marketcore/models_macro.py`; goldsilver facade re-exports; `NewsSource` loosened to `str`
- [x] T007 Create `src/marketcore/session.py` (tz-parameterized); `src/goldsilver/data/session.py` is now `stockholm_*` wrappers
- [x] T008 Create `src/marketcore/paths.py` with `config_base(app_name)` + path helpers; goldsilver `settings.py` calls them with `"goldsilver"` (path preserved)
- [x] T009 [P] Move `atomic_write_text` → `src/marketcore/fsutil.py`; facade in `src/goldsilver/fsutil.py`
- [x] T010 Extract `PollingService` base → `src/marketcore/services/base.py`
- [x] T011 Move `StockService` → `src/marketcore/services/stock_service.py` (PollingService subclass); decoupled name lookup via `register_names`
- [x] T012 Move news service → `src/marketcore/services/news_service.py`; `NewsService` now takes an injected `feeds` list
- [ ] T013 [P] (DEFERRED) Move `FxService`, `CommodityService`, `FuturesService`, `RealYieldService` → `src/marketcore/services/` — not needed by quantum
- [ ] T014 [P] (DEFERRED) Move `CalendarService`, `InsiderTradesService`, `CongressTradesService`, `StockTwitsService`, `OmxService`, `HistoryService`, `symbol_search` → `src/marketcore/services/`
- [ ] T015 [P] (DEFERRED) Move strategy/trade engine (`signal_strategies`, `alerts`, `backtest`, `trade_models`, `trades_service`) → `src/marketcore/strategies/`
- [ ] T016 [P] (DEFERRED) Move report engine → `src/marketcore/reports/` — needs metal-decoupling (METAL_LABELS / Swedish phases) first
- [x] T017 [P] Move generic widgets `chart`/`PriceChart`, `stock_tile`, `format` → `src/marketcore/widgets/`; facades left in goldsilver (fx/commodity/ratio tiles deferred with their services)
- [x] T018 Run full `uv run pytest` and confirm green (`marketcore/__init__` kept minimal to avoid eager textual/yfinance imports; public surface imported from submodules)

**Checkpoint**: `marketcore` is complete, importable with no app on the path, and the
existing `goldsilver` suite passes. Both user stories can now proceed.

---

## Phase 3: User Story 1 — goldsilver works unchanged (Priority: P1) 🎯 MVP

**Goal**: After extraction, `uv run goldsilver` behaves identically and reads/writes its
settings at the same path as before. Metal-specific code now sits cleanly on `marketcore`.

**Independent Test**: `uv run goldsilver` renders the same dashboard; `settings_path("goldsilver")`
equals the pre-refactor location; full suite green.

### Tests for User Story 1 ⚠️

- [x] T019 [P] [US1] Regression test `tests/marketcore/test_paths.py`: `settings_path("goldsilver")` equals the legacy location; invalid app-name rejected
- [x] T020 [P] [US1] Test `tests/marketcore/test_news_feeds.py`: `NewsService(feeds=[...])` stores injected feeds; goldsilver `NewsService()` defaults to its own feed list

### Implementation for User Story 1

- [ ] T021 [US1] (DEFERRED) Rebind `MetalsService` onto `PollingService` — currently still standalone in `src/goldsilver/data/service.py`, working and green; cosmetic
- [x] T022 [P] [US1] Extracted `NEWS_FEEDS` into `src/goldsilver/data/news_feeds.py`, injected via goldsilver's `NewsService` facade
- [x] T023 [P] [US1] Metal-specific config stays in `goldsilver` (presets, MetalPanel labels, prompt builder/constants untouched)
- [x] T024 [US1] goldsilver re-pointed to `marketcore.*` via facades; both app modules import cleanly
- [x] T025 [US1] Full `uv run pytest` green (207); `goldsilver` behaviour unchanged (settings path preserved, suite green)

**Checkpoint**: `goldsilver` fully functional on top of `marketcore`; Scenario 1 verified.

---

## Phase 4: User Story 2 — quantum dashboard (Priority: P2)

**Goal**: `uv run quantum` opens a TUI with quantum ETF headline tiles, a pure-play
quantum stock grid, and a quantum news feed — reusing `marketcore`.

**Independent Test**: `uv run quantum` mounts and renders the three regions; `q` exits 0;
quantum writes only under its own config dir.

### Tests for User Story 2 ⚠️

- [x] T026 [P] [US2] Smoke test `tests/quantum/test_app_mount.py`: mounts `QuantumApp` via `run_test()`, asserts tiles + news panel render, routes a quote (network stubbed via monkeypatched `start`)
- [x] T027 [P] [US2] Test `tests/quantum/test_config_isolation.py`: `settings_path("quantum") != settings_path("goldsilver")`; defaults verified

### Implementation for User Story 2

- [x] T028 [P] [US2] Created `src/quantum/data/presets.py`: `ETF_DEFAULTS` (`QTUM`,`ARKQ`), `PUREPLAY_DEFAULTS`, `ACCENT_PRESETS`, `NAME_OVERRIDES`
- [x] T029 [P] [US2] Created `src/quantum/data/news_feeds.py`: `QUANTUM_NEWS_FEEDS`
- [x] T030 [US2] Created `src/quantum/data/settings.py`: `QuantumSettings` + load/save via `marketcore.paths.*("quantum")`
- [x] T031 [US2] Created `src/quantum/app.py` (`QuantumApp`): one `StockService` feeds ETF tiles + pure-play grid, `NewsService(QUANTUM_NEWS_FEEDS)` → `QuantumNewsPanel`; `styles/app.tcss`
- [x] T032 [P] [US2] Created `src/quantum/__init__.py` + `__main__.py`
- [x] T033 [US2] Registered `quantum = "quantum:main"`; `uv sync` builds all three packages; `uv run quantum --help` works
- [x] T034 [US2] `tests/quantum` green; quantum smoke test renders all regions; stale-handler path intact

**Checkpoint**: Scenario 2 verified — quantum dashboard works independently of goldsilver.

---

## Phase 5: User Story 3 — third app on `marketcore` (Priority: P3)

**Goal**: A developer can build a new dashboard on `marketcore` without copying code out
of `goldsilver`; the import-direction invariant is enforced.

**Independent Test**: `python -c "import marketcore"` succeeds with no app on the path;
import-direction test passes; quickstart "add a third app" steps are accurate.

### Tests for User Story 3 ⚠️

- [x] T035 [P] [US3] `tests/marketcore/test_import_direction.py` fails if any `src/marketcore/**` file imports `goldsilver`/`quantum`
- [x] T036 [P] [US3] Added `tests/marketcore/test_public_api.py` importing the documented public surface

### Implementation for User Story 3

- [x] T037 [US3] Updated `CLAUDE.md` Repository Layout + Run section (three-package layout, both `uv run` targets, per-app config dirs)
- [x] T038 [US3] `quickstart.md` "Adding a third app" steps match the real layout (script registration, `marketcore.paths`, feed injection)

**Checkpoint**: Scenario 3 verified — the lower layer is reusable and guarded.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T039 [P] LoC budgets respected; justification headers added where a relocated file exceeds the cap (`marketcore/models_macro.py`, `marketcore/services/news_service.py`; `chart.py` kept its existing justification)
- [x] T040 [P] Every new `marketcore`/`quantum` module has a responsibility docstring + `from __future__ import annotations`
- [x] T041 Full `uv run pytest` green (207); both `goldsilver` and `quantum` app modules import cleanly; `uv run quantum --help` works. (Live interactive TUI launch not run headlessly; mount+render covered by the smoke test.)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: no dependencies — start immediately.
- **Foundational (Phase 2)**: depends on Setup — **BLOCKS both user stories**.
- **US1 (Phase 3)**: depends on Foundational (needs `PollingService`, `paths`, moved widgets/services).
- **US2 (Phase 4)**: depends on Foundational (needs `StockService`, `NewsService` feed injection, `paths`, widgets). Independent of US1.
- **US3 (Phase 5)**: depends on Foundational; best validated after US2 exists as the second consumer.
- **Polish (Phase 6)**: after all targeted stories.

### User Story Dependencies

- **US1 (P1)**: needs only Foundational. The MVP — proves the extraction did no harm.
- **US2 (P2)**: needs only Foundational. Does not depend on US1; can run in parallel with US1 once Phase 2 is done.
- **US3 (P3)**: needs Foundational; T036/T038 are most meaningful once US2 is the second consumer.

### Within the Foundational phase

- T004–T009 (leaf models/util/paths) before T010 (`PollingService`).
- T010 before T011–T014 (services subclass it).
- T011–T017 are largely independent file groups but several touch shared `goldsilver`
  import sites; T018 (curate `__init__` + full green) is the closing sequential gate.

### Parallel Opportunities

- Setup: T002, T003 in parallel.
- Foundational: T009 alongside T004–T008; T013, T014, T015, T016, T017 are different
  destination files and can parallelize, coordinating the shared import re-point at T018.
- US1 tests T019, T020 in parallel; T022, T023 in parallel.
- US2: T026, T027 in parallel; T028, T029, T032 in parallel; T030/T031 after presets/feeds.
- US3: T035, T036 in parallel.
- Once Phase 2 completes, US1 and US2 can be developed in parallel by different people.

---

## Parallel Example: User Story 2

```bash
# Tests together:
Task: "Smoke test QuantumApp mount in tests/quantum/test_app_mount.py"
Task: "Config isolation test in tests/quantum/test_config_isolation.py"

# Independent data files together:
Task: "Create src/quantum/data/presets.py (ETF + pure-play + accents)"
Task: "Create src/quantum/data/news_feeds.py (QUANTUM_NEWS_FEEDS)"
Task: "Create src/quantum/__init__.py + __main__.py"
```

---

## Implementation Strategy

### MVP First (US1 only)

1. Phase 1: Setup.
2. Phase 2: Foundational (the extraction) — CRITICAL, blocks everything.
3. Phase 3: US1 — verify `goldsilver` unchanged.
4. **STOP and VALIDATE**: `uv run goldsilver` + full suite green. This alone is a
   shippable, lower-risk refactor with no user-visible change.

### Incremental Delivery

1. Setup + Foundational → `marketcore` exists, goldsilver green.
2. US1 → goldsilver verified unchanged → ship the refactor (MVP).
3. US2 → `uv run quantum` works → ship the new app.
4. US3 → extensibility guards + docs → ship the platform.

---

## Notes

- [P] = different files, no dependency on an incomplete task.
- Keep moves mechanical (relocate + facade/re-point); do not rewrite working logic.
- Run `uv run pytest` after each Foundational move — the suite is the safety net.
- Do not collapse the goldsilver hybrid feed (`MetalsService` = goldprice.org + Avanza).
- Commit after each logical group (per project git policy — only when asked).
