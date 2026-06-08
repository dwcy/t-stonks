# Phase 0 Research: Hourly Claude-CLI Stock-Analysis Reports

All NEEDS CLARIFICATION items from Technical Context resolved below. The three big
forks (scheduler, data source, scope) were settled with the user before planning; the
rest are best-practice decisions for the chosen stack.

---

## D1 — How to invoke the Claude CLI headlessly

**Decision**: Run `claude -p "<prompt>"` (print mode) via
`asyncio.create_subprocess_exec`, one process per ticker per run, capturing stdout as
the HTML report. Grant only read/web tools:
`--allowed-tools WebSearch WebFetch Read`. Use `--output-format text` and instruct the
prompt to emit a complete HTML document and nothing else.

**Rationale**:
- Aligns with the `cli-llm-app` skill: reuse the user's existing subscription auth, no
  API key. Hourly cadence makes per-run cold-start (~seconds) irrelevant — the
  persistent-subprocess optimization in that skill targets sub-5s interactive turns,
  which we do not need.
- Print mode (`-p`) is the documented non-interactive path; it exits after one turn,
  which is exactly one report.
- Restricting tools keeps the run from touching the repo or running shell commands — it
  only reads the web. Least privilege for an unattended job.

**Alternatives considered**:
- **Anthropic API + SDK**: rejected — needs an API key and re-implements auth the CLI
  already has; contradicts repo CLAUDE.md "no credentials" posture.
- **Persistent `claude` subprocess (stream-json)**: rejected for v1 — added complexity
  (event-schema parsing, Windows `.cmd` resolution, keep-alive) with no benefit at an
  hourly cadence. Documented as a future optimization if run volume grows.
- **Let Claude `Write` the file itself** (grant Write, pass the path): rejected as
  primary — keeps path/format control in Python and avoids granting write access. The
  wrapper owns the filename scheme (FR-014); Claude only produces content.

**Open risk**: Claude may wrap output in ```` ```html ```` fences despite instructions →
mitigated by a deterministic fence-strip in `claude_runner.py` and a "starts with
`<!doctype`/`<html`" guard before save (see D5).

**Windows note**: on Windows the executable resolves to `claude.cmd`; resolve via
`shutil.which("claude")` and pass the resolved path to `create_subprocess_exec` (the
`cli-llm-app` skill's `.cmd` gotcha).

---

## D2 — Scheduling mechanism

**Decision**: An in-app `asyncio` background task started as a Textual worker
(`ReportScheduler`). It computes the delay to the next interval boundary (top of the
hour by default), `await asyncio.sleep(delay)`, fires the run, repeats. A re-entrancy
guard (an `asyncio.Lock` / "busy" flag per ticker) prevents overlap (FR-006). No missed
hours are backfilled (FR + assumption). Also exposed headlessly via
`python -m goldsilver.reports --once` for an external scheduler.

**Rationale**:
- The app already runs an `asyncio` event loop; a sleep-until-boundary loop is ~30 lines,
  zero new dependencies, and trivially cancellable on app exit.
- "Python scheduler in-repo" was the user's explicit choice over Windows Task Scheduler
  and cloud routines (reports must be written locally).
- Boundary alignment via `datetime.now(STOCKHOLM)` math gives "on the hour" without cron
  syntax.

**Alternatives considered**:
- **APScheduler (`AsyncIOScheduler`)**: rejected for v1 — a new dependency to get
  cron-on-the-hour we can do with `zoneinfo` + `asyncio.sleep`. Revisit only if we need
  persistence of missed jobs or multiple complex schedules. (Removed from the dependency
  list after this analysis.)
- **Windows Task Scheduler / cron calling `--once`**: rejected as primary (user choice)
  but the headless `--once` entrypoint deliberately keeps this door open as a fallback —
  documented in quickstart.
- **`textual`'s `set_interval`**: usable, but a raw `asyncio` task gives cleaner
  boundary-alignment and cancellation semantics and keeps scheduling logic outside the
  App class (testable in isolation).

---

## D3 — Where live market data comes from

**Decision**: The headless Claude run gathers all macro/market data itself via
`WebSearch`/`WebFetch` at runtime (USD/SEK, DXY, US futures, yields, European indices,
gold/silver, geopolitics, economic calendar, the instrument's own quote/technicals). The
report engine passes **no** price data from the TUI's feeds.

**Rationale**:
- User's explicit choice ("claude pulls live via web"). Keeps the engine decoupled from
  the TUI's hybrid feed and from yfinance — the analyzer is self-contained and works the
  same when run headlessly.
- Avoids the repo CLAUDE.md trap of coupling more surfaces to the goldprice/Avanza
  hybrid.

**Alternatives considered**:
- **Feed an app snapshot (goldprice/Avanza/yfinance JSON) into the prompt**: rejected —
  more moving parts, couples the report to live-feed availability, and the user picked
  the pure-web option.

**Consequence**: the prompt must instruct Claude to **state which data it could not
retrieve** rather than invent numbers (edge case), and to timestamp its data.

---

## D4 — Swedish session phase + US-market-state derivation

**Decision**: A pure function module `reports/phase.py` maps a `Europe/Stockholm`
datetime to a session phase and an inferred US-market state, reusing `data/session.py`'s
`STOCKHOLM` tz and the constants in `data/trading_hours.py`.

Swedish phase bands (from the user's observations, expressed as *phase labels*, not
hard verdicts — the prompt tests them):

| Stockholm local time | Phase label |
|---|---|
| 09:00–10:00 | `MORNING_STRENGTH` |
| 10:00–12:00 | `MIDDAY_WEAKNESS` |
| 12:00–14:30 | `TREND_FOLLOWING` |
| 14:30–17:30 | `US_INFLUENCE` |
| 17:30–close (22:54) | `US_DOMINATED` |
| outside 08:00–22:54 | `CLOSED` |

US-market state, inferred from Stockholm time (US cash session 09:30–16:00 ET ≈
15:30–22:00 CET during EU summer):

| Stockholm local time | US state |
|---|---|
| before ~13:30 | `CLOSED` (overnight) |
| ~13:30–15:30 | `PRE_MARKET` |
| ~15:30 (±) | `OPENING` |
| ~15:30–22:00 | `OPEN` |
| ~22:00–22:30 | `NEAR_CLOSE` |
| after ~22:30 | `CLOSED` |

**Rationale**: pure + table-driven → unit-testable without a clock (`test_report_phase`
passes synthetic datetimes). The ET↔CET offset shifts by one hour across the US/EU DST
gap; the function derives US session edges from an actual `America/New_York` `zoneinfo`
conversion rather than hardcoding CET, so the boundaries stay correct year-round.

**Alternatives considered**:
- **Hardcode CET boundaries**: rejected — breaks for ~3 weeks/year when US and EU DST
  are misaligned. Deriving from `America/New_York` is exact.

---

## D5 — Guaranteeing valid standalone HTML

**Decision**: Three-layer guard in `claude_runner.py` / `html_writer.py`:
1. Prompt demands: "Output ONLY a complete HTML5 document with inline `<style>`; no
   markdown, no code fences, no commentary."
2. `claude_runner` strips a leading/trailing ```` ``` ```` / ```` ```html ```` fence if
   present.
3. `html_writer` validates the payload starts (case-insensitive, after whitespace) with
   `<!doctype html` or `<html`; if not, it wraps the raw text in a minimal HTML error
   shell and marks the run `MALFORMED` rather than writing a broken file.

**Rationale**: makes SC-003 ("100% open as valid HTML") robust to model formatting drift
without parsing the whole document.

**Alternatives considered**:
- **Trust the model**: rejected — fencing is a known LLM behavior; a cheap guard removes
  the whole failure class.
- **Full HTML parse/validation (e.g. `lxml`)**: rejected — overkill, new dep; a prefix
  guard is sufficient for "is this a document".

---

## D6 — Report file path & index scheme

**Decision**: `reports/<YYYY-MM-DD>/<HH-MM>-<SAFE_TICKER>.html` in Stockholm local time,
relative to repo root. `SAFE_TICKER` is the symbol uppercased with `/`, `.`, ` `, `:`
replaced by `-` (so `LUG.ST` → `LUG-ST`, `XAU` → `XAU`). After each run, regenerate
`reports/index.html`: dates as `<h2>` sections newest-first, each report a relative
`<a href>` with phase/verdict shown if cheaply parseable from a sidecar.

**Decision (verdict capture)**: write a tiny sidecar `<HH-MM>-<TICKER>.json`
(`ReportRun` serialized: ticker, time, status, verdict, confidence, duration) next to the
HTML so the index and the TUI recent-list can show verdict/confidence without parsing
HTML. The prompt is asked to also emit a `<!-- VERDICT: {json} -->` comment as the first
line for a parse fallback.

**Rationale**: date-foldering matches the user's `reports/[date]/time.html` request;
per-ticker suffix avoids collisions when several instruments run in the same minute
(SC + concurrency edge case). The sidecar keeps the index generator and TUI off the HTML
body.

**Alternatives considered**:
- **`time.html` with no ticker suffix**: rejected — collides when the watchlist has >1
  instrument in the same minute.
- **Parse the HTML to get the verdict for the index**: rejected — brittle; the sidecar is
  authoritative and cheap.

---

## D7 — Prompt asset vs Claude Code skill vs subagent

**Decision**: Ship the analysis framework as a **versioned prompt template file**
(`reports/prompts/analysis_prompt.md`) with `{PLACEHOLDER}` substitution, passed inline
to `claude -p`. Not a `.claude/skills/*` skill, not a subagent.

**Rationale**:
- Headless `claude -p` runs outside an interactive session; project skills/subagents are
  surfaced to the interactive agent loop and are not guaranteed to load for a one-shot
  print run. A self-contained prompt is deterministic and version-controllable.
- The template doubles as the human-readable spec of the framework (contract
  `analysis-prompt.md`) and can be edited without touching Python.

**Alternatives considered**:
- **`.claude/skills/stock-analyzer/SKILL.md`**: useful for *interactive* "analyze X" in a
  dev session; noted as an optional future mirror, but not the engine's source of truth.
- **A subagent (`Task`)**: irrelevant to a headless external invocation.

---

## D8 — The analysis framework content (assumption-testing core + enhancements)

**Decision**: The template encodes, in priority order:
1. **Market Reaction Validation (highest priority)** — treat every assumption below as a
   hypothesis; verify against today's actual price action; observed reaction always
   overrides theory.
2. **Trader Assumptions To Test** — Swedish session structure, US-market assumptions
   (USD stability, "good news can be bad", rate hikes/cuts), gold/silver vs USD & real
   yields, geopolitical safe-haven behavior — each phrased "test whether… and if not,
   name the dominant driver".
3. **Enhancements** folded in from the comparison research: Market Regime Detection,
   Capital/Sector Flow, European Market Influence (STOXX/DAX/OMX), Bond Market Analysis
   (US 2Y/10Y, Bund, SE yields), Positioning, Breadth, **Correlation Validation** (the
   single most valuable addition — USD↔Gold, Yields↔Growth, VIX↔Equities, Nasdaq↔OMX:
   intact / weakening / broken), Scenario Analysis (bull/neutral/bear probabilities = 100%),
   Next Catalyst, Trade-Timing by Swedish clock.
4. **Fixed final summary block** (the exact output format the HTML must render).

**Rationale**: directly implements the user's iterated prompt (the "test, don't assert"
correction) plus the 10 hedge-fund-checklist enhancements they asked to fold in. Full
required structure is the `analysis-prompt.md` contract.

---

## D9 — Settings shape

**Decision**: Add a nested `ReportSettings` dataclass to `AppSettings` mirroring the
existing `SimulatorSettings` pattern (slots, `__post_init__` validation, defaults via
`field(default_factory=...)`): `enabled: bool=False`, `interval_minutes: int=60`,
`report_tickers: list[str]=[]` (stocks only; metals pinned in code),
`timeout_seconds: int=180`, `allowed_tools: list[str]=["WebSearch","WebFetch","Read"]`,
`out_dir: str="reports"`. Validated and round-tripped by the existing `load`/`save`.

**Rationale**: reuses the proven, tested settings pattern; no new persistence; defaults
keep the scheduler **off** until the user opts in (safe default for a job that spawns
processes). Metals are pinned in engine code, not stored, so they can never be removed.

**Alternatives considered**:
- **Reuse `stock_tickers`**: rejected — that list drives the chart mini-tiles; report
  watchlist is a distinct concern and should be independently editable.
- **Separate JSON file**: rejected — `AppSettings` already centralizes config; a second
  file fragments it.

---

## D10 — Surfacing the clickable link in a TUI

**Decision**: On run completion the service posts a Textual message; the watchlist modal
(and a footer toast) shows the report with an OSC-8 hyperlink / Textual `@click` action
that calls `webbrowser.open(path.as_uri())`. The recent-reports list in the modal lists
the last N runs with verdict/confidence from the sidecar.

**Rationale**: "click to open" in a terminal = either an OSC-8 hyperlink (supported by
Windows Terminal) or an Enter-to-open action; both resolve to `webbrowser.open`. Reuses
the reactive/message pattern mandated by repo CLAUDE.md.

**Alternatives considered**:
- **Print a raw path**: works but not "clickable"; kept as the headless-mode output.
- **Auto-open every report in the browser**: rejected — hourly auto-opening browser tabs
  is hostile; opening is user-initiated.
