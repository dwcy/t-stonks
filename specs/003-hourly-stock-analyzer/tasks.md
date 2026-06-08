---

description: "Task list for Automated Hourly Claude-CLI Stock-Analysis HTML Reports"
---

# Tasks: Automated Hourly Claude-CLI Stock-Analysis HTML Reports

**Input**: Design documents from `specs/003-hourly-stock-analyzer/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Tests**: INCLUDED. The plan enumerates concrete test modules and `~/.claude/rules/python.md`
mandates a mount-and-render smoke test for every custom Textual widget. Test tasks are
written before/with their implementation per story.

**Organization**: grouped by user story. US1 and US2 are both P1; US1 is the smallest
standalone MVP, US2 is the core analysis pipeline.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no incomplete-task dependency)
- **[Story]**: US1–US5, mapping to spec.md user stories
- Exact file paths included

## Path Conventions

Single project — code under `src/goldsilver/`, tests under `tests/` at repo root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: package skeleton and artifact ignores.

- [x] T001 Create the report engine package: `src/goldsilver/reports/__init__.py` (module-intent docstring) and the `src/goldsilver/reports/prompts/` directory, per plan.md structure
- [x] T002 [P] Add generated `reports/` to `.gitignore` (already committed in `01b3067`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: shared models, settings, and pure clock logic every story depends on.

**⚠️ CRITICAL**: no user story work begins until this phase is complete.

- [x] T003 [P] Create `src/goldsilver/reports/constants.py` — `PINNED_METALS = ("XAU","XAG")`, metal labels, `DEFAULT_ALLOWED_TOOLS`, `TEMPLATE_VERSION`, `DEFAULT_MAX_CONCURRENCY = 3`, and the `safe_name` symbol→filename rule (`/ . space :` → `-`)
- [x] T004 [P] Create `src/goldsilver/reports/models.py` — `ReportStatus`, `SwedishPhase`, `USMarketState` str-enums; `ReportTicker` dataclass (`symbol`, `label`, `pinned`, `kind`, `safe_name`); Pydantic v2 `Verdict` and `ReportRun` models (per data-model.md)
- [x] T005 [P] Implement `src/goldsilver/reports/phase.py` — pure `swedish_phase(dt)` and `us_market_state(dt)` taking a `Europe/Stockholm`-aware datetime, deriving US session edges from an `America/New_York` `zoneinfo` conversion (DST-correct); reuse `STOCKHOLM` from `data/session.py`
- [x] T006 Add nested `ReportSettings` dataclass to `src/goldsilver/data/settings.py` and a `report` field on `AppSettings` — fields `enabled`, `interval_minutes`, `report_tickers`, `timeout_seconds`, `max_concurrency`, `allowed_tools`, `out_dir` with `__post_init__` clamping/dedup (mirror `SimulatorSettings`); ensure `load`/`save` round-trip the nested dataclass
- [x] T007 [P] Unit test `tests/test_report_phase.py` — synthetic datetimes across every Swedish band and US-state band, including a US/EU DST-misalignment date, plus the `safe_name` mapping

**Checkpoint**: shared types, settings, and clock logic ready.

---

## Phase 3: User Story 1 - Manage the report watchlist from the TUI (Priority: P1) 🎯 MVP

**Goal**: curate the list of instruments to report on, from inside the TUI, persisted; Gold/Silver pinned.

**Independent Test**: launch TUI → open watchlist → add `NVDA`, try to remove Gold (rejected), remove a stock → quit/relaunch → changes survive.

### Tests for User Story 1

- [x] T008 [P] [US1] Textual smoke test `tests/test_report_watchlist.py` — `App.run_test()` mounts the modal with ≥1 `pilot.pause()`; asserts pinned metals are present and non-removable, a valid ticker adds, blank/duplicate is dropped, and the change is written to `AppSettings.report.report_tickers`

### Implementation for User Story 1

- [x] T009 [US1] Implement `src/goldsilver/widgets/report_watchlist.py` — a `ModalScreen` listing `report_tickers` plus pinned `PINNED_METALS` rows; add/remove inputs; reject removing pinned metals with a hint; dedup/blank-drop; save via `AppSettings.save()`. Helpers named by role (`_build_*`, `_collect_*`), never `_render*`/`_compose*` (python.md Textual rule)
- [x] T010 [US1] Bind a watchlist key (e.g. `R`) and `push_screen(ReportWatchlist())` in `src/goldsilver/app.py`; add the binding to the footer
- [x] T011 [P] [US1] Add modal styling for the watchlist screen in `src/goldsilver/styles/app.tcss`

**Checkpoint**: watchlist is fully usable and persists, with no analysis engine yet.

---

## Phase 4: User Story 2 - Generate a report on demand and open it (Priority: P1)

**Goal**: produce one self-contained HTML report per instrument via the Claude CLI, in bounded parallel, and open it from a clickable link.

**Independent Test**: from the TUI press "generate now" → files appear at `reports/<date>/<HH-MM>-<TICKER>.html` → activating the link opens the report in the browser; a failing ticker does not stop the others.

### Tests for User Story 2

- [x] T012 [P] [US2] Test `tests/test_prompt_builder.py` — every `{PLACEHOLDER}` is substituted (none left), the `<!-- TEMPLATE_VERSION -->` line is stripped before send, and literal `{`/`}` in CSS/JSON examples survive (no `.format()`)
- [x] T013 [P] [US2] Test `tests/test_claude_runner.py` — `claude` mocked: happy path returns stripped HTML + `SUCCESS`; ```` ```html ```` fences stripped; timeout → `TIMEOUT`; missing CLI (`which` → None) → `CLI_MISSING`; non-HTML output → `MALFORMED`; non-zero exit → `ERROR`
- [x] T014 [P] [US2] Test `tests/test_html_writer.py` — path scheme `reports/<date>/<HH-MM>-<SAFE_TICKER>.html`, `safe_name` cases (`LUG.ST`→`LUG-ST`), HTML-prefix guard (SUCCESS vs MALFORMED error shell), sidecar `.json` matches the `ReportRun`

### Implementation for User Story 2

- [x] T015 [P] [US2] Author the prompt template `src/goldsilver/reports/prompts/analysis_prompt.md` exactly per `contracts/analysis-prompt.md` — `<!-- TEMPLATE_VERSION: 1 -->` line, all 7 placeholders, the Market-Reaction-Validation-first framework, correlation table, scenario probabilities, enhancements, and the fixed final-summary + line-1 `<!-- VERDICT: {json} -->` requirement
- [x] T016 [P] [US2] Implement `src/goldsilver/reports/prompt_builder.py` — `AnalysisPromptContext` dataclass + `build_prompt(context)`: load template, strip the version line, literal `str.replace` over the known placeholder set
- [x] T017 [US2] Implement `src/goldsilver/reports/claude_runner.py` — `shutil.which("claude")` (Windows `.cmd`), `asyncio.create_subprocess_exec` with `--output-format text --allowed-tools …`, `asyncio.wait_for(timeout)`, fence-strip, line-1 VERDICT parse → `Verdict|None`, map outcomes to `ReportStatus` (per claude-cli-invocation contract). Depends on T004
- [x] T018 [US2] Implement `src/goldsilver/reports/html_writer.py` — `write_report(run, html)`: HTML-prefix guard, write report HTML (or error shell on `MALFORMED`) + sidecar `ReportRun` JSON at the dated path (per report-file contract). Depends on T003, T004
- [x] T019 [US2] Implement `src/goldsilver/reports/report_service.py` — `run_one(ticker)` and `run_all(watchlist)`: build context (uses `phase.py`), `asyncio.gather` bounded by `asyncio.Semaphore(max_concurrency)` with `return_exceptions=True`, per-ticker no-overlap guard, collect `ReportRun`s. Depends on T016, T017, T018, T005
- [x] T020 [US2] Implement headless entrypoint `src/goldsilver/reports/__main__.py` — argparse `--all/--ticker/--once/--concurrency/--timeout/--out/--no-index/--json`, calls `report_service`, prints per-ticker lines or `--json`, exit codes 0/2/3/4 (per report-runner-cli contract). Depends on T019
- [x] T021 [US2] Add a "generate now" action in `src/goldsilver/app.py` (run `report_service.run_all` in a Textual worker), handle the run-result message, and open a finished report via `webbrowser.open(path.as_uri())`; surface each finished report as a clickable OSC-8 link / Enter-to-open row in the watchlist modal. Depends on T019, T009

**Checkpoint**: on-demand reports generate in parallel and open from a link; the analysis framework already ships here.

---

## Phase 5: User Story 5 - Analysis tests assumptions, not asserts them (Priority: P2)

**Goal**: enforce that reports validate macro assumptions against today's reaction and carry a structured verdict.

**Independent Test**: inspect a generated report — each macro driver has an assumption-vs-actual line, broken correlations are flagged, and the line-1 VERDICT parses into the `Verdict` model.

- [x] T022 [P] [US5] Test `tests/test_analysis_framework.py` — assert `analysis_prompt.md` contains the "Market Reaction Validation — HIGHEST PRIORITY" section, the Correlation Validation table, scenario-probabilities-sum-to-100, and each enhancement heading; assert a sample line-1 `<!-- VERDICT: {…} -->` comment parses into a valid `Verdict`
- [x] T023 [US5] Harden verdict handling in `src/goldsilver/reports/claude_runner.py` + `html_writer.py` — tolerant parse (missing/invalid VERDICT → `verdict=None`, status stays `SUCCESS`), and ensure the saved report body keeps the color-coded verdict card; record `verdict`/`confidence` in the sidecar for downstream surfaces. Depends on T017, T018

**Checkpoint**: report quality is enforced by tests and tolerant parsing.

---

## Phase 6: User Story 3 - Automatic hourly runs while the app is open (Priority: P2)

**Goal**: fire a full-watchlist run once per interval, aligned to the hour, no overlap, no backfill.

**Independent Test**: set a short interval, leave the app running across two boundaries → two timestamped report sets appear unattended; toggling off stops runs.

- [x] T024 [US3] Implement `src/goldsilver/reports/scheduler.py` — `ReportScheduler`: compute delay to the next interval boundary in `Europe/Stockholm`, `asyncio` sleep-fire-repeat loop, cancellable on exit, skipping a boundary while a run is in flight (no backfill). Depends on T019
- [x] T025 [US3] Start the scheduler as a Textual worker when `settings.report.enabled` and add an enable + interval control to the watchlist modal in `src/goldsilver/app.py` / `src/goldsilver/widgets/report_watchlist.py`. Depends on T024, T009
- [x] T026 [P] [US3] Test `tests/test_scheduler.py` — next-boundary delay math at sample clock times; a boundary during an in-flight run is skipped; disabled → no run (subprocess layer mocked)

**Checkpoint**: unattended hourly reports run while the app is open.

---

## Phase 7: User Story 4 - Reports browsable as a dated archive (Priority: P3)

**Goal**: a regenerated `reports/index.html` and an in-TUI recent list.

**Independent Test**: after runs across ≥2 dates, open `reports/index.html` → all reports linked, grouped by date newest-first.

- [x] T027 [US4] Add `write_index(out_dir)` to `src/goldsilver/reports/html_writer.py` — scan `reports/*/*.json`, group by date `<h2>` newest-first, color-coded verdict links, `—` for null verdict, status badge for failures, empty-state placeholder; call it once after `gather` settles in `report_service` and honor `--no-index`. Depends on T018, T019
- [x] T028 [P] [US4] Add a recent-reports list (last N runs from sidecars, with verdict/confidence) to `src/goldsilver/widgets/report_watchlist.py`. Depends on T009, T018
- [x] T029 [P] [US4] Test `tests/test_report_index.py` — date grouping/order, verdict badge + confidence, null verdict shows `—`, empty state when no reports

**Checkpoint**: history is browsable in the browser and the TUI.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [x] T030 [P] Cross-link the report engine from `README.md` and confirm `specs/003-hourly-stock-analyzer/quickstart.md` steps are accurate
- [x] T031 Run `uv run pytest` (full suite green), `uv tree` (confirm zero new third-party deps — scheduling is stdlib), and audit new files against `python.md` LoC budgets
- [~] T032 Manual `quickstart.md` validation end-to-end — headless live run validated (real `claude` CLI invocation, capture, file write, timeout handling all confirmed); in-UI generate/open is a manual check left to the user

---

## Dependencies & Execution Order

### Phase order

- **Setup (P1 tasks T001–T002)** → **Foundational (T003–T007)** blocks everything →
  **US1 (T008–T011)** and **US2 (T012–T021)** (both P1) → **US5 (T022–T023)** →
  **US3 (T024–T026)** → **US4 (T027–T029)** → **Polish (T030–T032)**.

### Story dependencies

- **US1 (P1)**: needs Foundational only. Standalone MVP — no engine required.
- **US2 (P1)**: needs Foundational; T021 also touches the US1 modal (link surfacing).
- **US5 (P2)**: refines US2's prompt/verdict path — needs US2.
- **US3 (P2)**: needs US2's `report_service` (T019) to schedule.
- **US4 (P3)**: needs US2's `html_writer`/sidecars (T018) and the US1 modal (T028).

### Shared-file sequencing (NOT parallel across these)

- `src/goldsilver/app.py`: T010 (US1) → T021 (US2) → T025 (US3) — sequential.
- `src/goldsilver/widgets/report_watchlist.py`: T009 (US1) → T021/T025 (link+toggle) → T028 (US4) — sequential.
- `src/goldsilver/reports/html_writer.py`: T018 (US2) → T023 (US5) → T027 (US4) — sequential.
- `src/goldsilver/reports/claude_runner.py`: T017 (US2) → T023 (US5) — sequential.

### Within a story

- Tests marked [P] are independent of each other and can be written together.
- Models/template/builder before the service that composes them; service before the
  entrypoint and the UI trigger.

---

## Parallel Opportunities

- **Setup/Foundational**: T002, then T003 + T004 + T005 + T007 in parallel (distinct files); T006 after (independent file, no [P] conflict but logically grouped).
- **US2 tests**: T012 + T013 + T014 together; **US2 build**: T015 + T016 together, then T017/T018 in parallel (distinct modules), then T019.
- **Across stories** once Foundational is done: US1 (T008–T011) and the US2 engine modules (T012–T020) can progress in parallel by different developers; only the shared `app.py`/modal/writer touchpoints listed above must serialize.

### Parallel example — Foundational

```bash
Task: "Create reports/constants.py"           # T003
Task: "Create reports/models.py"              # T004
Task: "Implement reports/phase.py"            # T005
Task: "Unit test tests/test_report_phase.py"  # T007
```

### Parallel example — US2 engine modules

```bash
Task: "Author prompts/analysis_prompt.md"     # T015
Task: "Implement reports/prompt_builder.py"   # T016
# then:
Task: "Implement reports/claude_runner.py"    # T017
Task: "Implement reports/html_writer.py"      # T018
```

---

## Implementation Strategy

### MVP first

1. Setup + Foundational (T001–T007).
2. **US1** (T008–T011) → validate: curate the watchlist, persistence survives restart. Demo.

### Incremental delivery

3. **US2** (T012–T021) → on-demand parallel reports + open link (the analysis ships here). Demo.
4. **US5** (T022–T023) → quality enforced by tests + tolerant verdict parse.
5. **US3** (T024–T026) → unattended hourly automation. Demo.
6. **US4** (T027–T029) → browsable `index.html` + TUI recent list. Demo.
7. **Polish** (T030–T032) → full suite, dep audit, manual quickstart.

### Notes

- [P] = different files, no incomplete-task dependency.
- `claude` is mocked in `test_claude_runner.py`/`test_scheduler.py` — no live CLI calls in CI.
- Commit after each task or logical group; stop at any checkpoint to validate a story.
- The CLI is granted web/read tools only — never `Write`/`Bash`; the engine never trades.
