# Implementation Plan: Automated Hourly Claude-CLI Stock-Analysis HTML Reports

**Branch**: `003-hourly-stock-analyzer` | **Date**: 2026-06-08 | **Spec**: `specs/003-hourly-stock-analyzer/spec.md`
**Input**: Feature specification from `specs/003-hourly-stock-analyzer/spec.md`

## Summary

Add an in-app **report engine** to the existing Textual TUI that, once per hour (and on
demand), shells out to the **Claude CLI in headless print mode** to produce a
self-contained HTML stock-analysis report per watchlist instrument, saved to
`reports/<date>/<time>-<ticker>.html` and surfaced as a clickable link.

The list of instruments is curated from a new **watchlist editor screen** inside the TUI;
Gold (`XAU`) and Silver (`XAG`) are always analyzed and pinned. Scheduling runs as an
`asyncio` background task on the app's own event loop (no extra daemon, no Windows Task
Scheduler), and the same run path is exposed as a headless CLI entrypoint
(`python -m goldsilver.reports`) so an external scheduler can drive it if wanted.

The analysis itself is defined by a **versioned prompt template** (a repo asset, not an
interactive skill — headless `claude -p` needs a self-contained prompt). Its defining
property: every macro assumption ("strong USD pressures gold", "rate hikes are bearish",
"war in Iran is bad for gold") is treated as a **hypothesis to validate against today's
actual price action**, with broken correlations flagged and the dominant alternative
driver named. The framework folds in regime detection, sector/capital flow, European
indices, bond/yield analysis, positioning & breadth, correlation validation, scenario
probabilities, next-catalyst, and an explicit Swedish-clock trade-timing assessment.

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: Textual 8.x (TUI + `work`/`asyncio` workers), Pydantic v2
(report models), stdlib `asyncio.create_subprocess_exec` + `asyncio` interval loop for
scheduling, `webbrowser`, `zoneinfo`. **External tool**: `claude` CLI on `PATH`
(subscription auth). *(An `apscheduler` dependency was considered and rejected — see
research.)*
**Storage**: HTML files under repo-local `reports/`; config persisted in the existing
`AppSettings` JSON (`settings.json` under the OS config dir). No database.
**Testing**: pytest + pytest-asyncio (existing dev group); Textual `App.run_test()` /
`Pilot` smoke tests for the new screen; subprocess mocked for run-path tests.
**Target Platform**: Windows Terminal + Linux (Textual cross-platform); reports open in
the host's default browser.
**Project Type**: single-process Textual TUI desktop app (unchanged).
**Performance Goals**: per-ticker run ≤3 min (default timeout); scheduler tick overhead
negligible; report write + index regen ≤1 s; on-demand link appears immediately on
completion.
**Constraints**: no backend, no DB, no API key (reuse CLI login per the `cli-llm-app`
skill), no blocking calls on the event loop (subprocess must be async), reports must be
valid standalone HTML, git-ignore `reports/`.
**Scale/Scope**: 2 pinned metals + 0–~12 watchlist tickers; 1 new screen, 1 scheduler, 1
report service, 1 prompt builder, 1 HTML/index writer, 1 headless entrypoint, 1 settings
extension; ~6 new files, ~3 modified.

## Constitution Check

*GATE: must pass before Phase 0. The project constitution
(`.specify/memory/constitution.md`) is still the unfilled placeholder template — no
ratified principles to gate against. Per the precedent set in
`specs/002-charts-and-stock-tiles/plan.md`, fall back to the repository `CLAUDE.md`, the
user's global `CLAUDE.md`, and `~/.claude/rules/python.md` as the de-facto constitution:*

| Rule (de-facto constitution) | This plan complies |
|---|---|
| No backend / REST server / persistence layer (repo CLAUDE.md) | Single-process TUI + local files only. No server, no DB. ✅ |
| Don't drop the hybrid feed / don't parse with `.get()` chains | The CLI gathers macro data via web; the TUI's price feeds are untouched. Report payloads that re-enter Python are Pydantic-modeled, not `.get()`-walked. ✅ |
| Async-first; no blocking I/O on the event loop (python.md) | `asyncio.create_subprocess_exec` for the CLI; scheduler is an `asyncio` task; file writes are short and chunked off the tick. ✅ |
| Reactive widgets; never `refresh()` from outside (repo CLAUDE.md) | New screen uses reactives + posts messages; run results delivered via `post_message`. ✅ |
| Settings via the existing typed store, no hardcoded config (python.md) | New `ReportSettings` dataclass nested in `AppSettings`, same load/validate pattern as `SimulatorSettings`. ✅ |
| `from __future__ import annotations`, `pathlib`, no `import *`, file-intent docstring (python.md) | All new modules follow these. ✅ |
| LoC budgets: lib ≤200/400, screen ≤250/400, script ≤150/250 (python.md) | Work split across service / builder / writer / screen / scheduler modules to stay under soft caps — see Structure. ✅ |
| Textual override-shadow rules (python.md) | New widget helpers named by role (`_build_*`, `_collect_*`), never `_render*`/`_compose*`; one `run_test()` smoke test added. ✅ |
| Latest stable versions; no deprecated APIs (global CLAUDE.md) | stdlib-only scheduling; `zoneinfo` not `pytz`; verify deps with `uv tree`. ✅ |
| No comments explaining WHAT; no dead code/TODOs (global CLAUDE.md) | Enforced in task authoring. ✅ |

**Result**: PASS. No violations → Complexity Tracking left empty.

## Project Structure

### Documentation (this feature)

```text
specs/003-hourly-stock-analyzer/
├── plan.md              # This file (/speckit-plan output)
├── spec.md              # Feature spec
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── report-runner-cli.md       # headless entrypoint contract
│   ├── claude-cli-invocation.md   # how `claude` is shelled out
│   ├── analysis-prompt.md         # the prompt template + required output structure
│   └── report-file.md             # path scheme + HTML/index contract
└── tasks.md             # /speckit-tasks output (NOT created here)
```

### Source Code (repository root)

New code lives under the existing `src/goldsilver/` package. A new `reports/` subpackage
isolates the report engine; the TUI screen lives under `widgets/` next to its peers;
output artifacts go in a repo-root `reports/` data folder (git-ignored).

```text
src/goldsilver/
├── app.py                         # MODIFIED: start ReportScheduler worker; bind watchlist key; route run-result messages
├── data/
│   ├── settings.py                # MODIFIED: add nested ReportSettings (enabled, interval, report_tickers, timeout, max_concurrency, allowed_tools, out_dir)
│   ├── session.py                 # REUSED: Europe/Stockholm tz
│   └── trading_hours.py           # REUSED/EXTENDED: derive Swedish session phase + US-market-state helpers
├── reports/                       # NEW subpackage — the report engine
│   ├── __init__.py
│   ├── models.py                  # Pydantic/dataclass: ReportRun, ReportStatus, ReportTicker
│   ├── phase.py                   # Swedish session phase + US-market-state derivation (pure, testable)
│   ├── prompt_builder.py          # load template, substitute AnalysisPromptContext
│   ├── claude_runner.py           # async subprocess wrapper around `claude -p` (+ fence-strip)
│   ├── report_service.py          # orchestrates: gather(Semaphore) per-ticker → build prompt → run CLI → write file → status
│   ├── html_writer.py             # write report HTML + (re)generate reports/index.html
│   ├── scheduler.py               # asyncio interval scheduler (on-the-hour alignment, no overlap)
│   ├── prompts/
│   │   └── analysis_prompt.md     # the versioned Swedish-trader prompt template (the "skill")
│   └── __main__.py                # headless entrypoint: `python -m goldsilver.reports [--ticker X | --all] [--once]`
├── widgets/
│   └── report_watchlist.py        # NEW: Textual ModalScreen to manage report tickers + show recent report links
└── styles/
    └── app.tcss                   # MODIFIED: styles for the watchlist modal

reports/                            # NEW (git-ignored): reports/<YYYY-MM-DD>/<HH-MM>-<TICKER>.html + index.html

tests/
├── test_report_phase.py           # NEW: Swedish phase / US-state derivation (pure unit)
├── test_prompt_builder.py         # NEW: placeholder substitution + template integrity
├── test_claude_runner.py          # NEW: subprocess mocked; fence-strip; timeout path
├── test_html_writer.py            # NEW: path scheme, valid-HTML guard, index grouping/order
└── test_report_watchlist.py       # NEW: Textual run_test() smoke + pinned-metals rule
```

**Structure Decision**: keep the engine as a cohesive `goldsilver.reports` subpackage so
the TUI depends on a thin service surface (`report_service.run_*`) and never touches
`subprocess` directly — satisfies python.md split-pattern #1 (service module) and keeps
each file under its LoC soft cap. The prompt lives as a **template asset**
(`reports/prompts/analysis_prompt.md`) rather than a `.claude/` skill because headless
`claude -p` does not reliably auto-load interactive skills; an optional mirror skill can
be added later for interactive use without changing the engine.

## Complexity Tracking

> No Constitution Check violations — section intentionally empty.
