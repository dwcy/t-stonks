# Feature Specification: Automated Hourly Claude-CLI Stock-Analysis HTML Reports

**Feature Branch**: `003-hourly-stock-analyzer`
**Created**: 2026-06-08
**Status**: Draft
**Input**: User description: automatic hourly triggering of the Claude CLI that
generates a clickable HTML stock-analysis report saved to
`reports/[date]/time.html`, driven by a UI-managed watchlist of tickers, using a
Swedish-trader analysis framework that **tests** its macro assumptions against
actual market reactions rather than asserting them.

## Clarifications

Resolved interactively before planning:

- **Trigger mechanism**: in-repo Python scheduler (not Windows Task Scheduler, not a
  cloud routine), so report files land in the local `reports/` folder.
- **Market data**: the headless Claude run gathers live data itself via web tools
  (`WebSearch` / `WebFetch`) at runtime — no coupling to the TUI's own price feeds.
- **Scope**: generic, ticker-driven analyzer. Gold (`XAU`) and Silver (`XAG`) are
  always analyzed; additional instruments come from a **UI-managed watchlist**.
- **Watchlist UI**: the user manages the list of report tickers from inside the TUI.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Manage the report watchlist from the TUI (Priority: P1)

As the operator, I open a watchlist editor inside the running TUI, add or remove
stock tickers (e.g. `LUG.ST`, `VOLV-B.ST`, `NVDA`), and the list persists. Gold and
Silver are always included and cannot be removed. This is the list the hourly job
reports on.

**Why this priority**: Without a managed list there is nothing to report on. It is the
smallest slice that delivers value on its own — even with no automation, the user can
curate exactly which instruments matter.

**Independent Test**: Launch the TUI, open the watchlist editor, add `NVDA`, remove a
stock, quit and relaunch — the changes survive. Gold/Silver remain pinned.

**Acceptance Scenarios**:

1. **Given** the TUI is running, **When** the user presses the watchlist key, **Then**
   an editor appears listing current report tickers plus the pinned Gold/Silver rows.
2. **Given** the editor is open, **When** the user adds a valid ticker, **Then** it
   appears in the list and is written to persisted settings on save.
3. **Given** the editor is open, **When** the user tries to remove Gold or Silver,
   **Then** the action is rejected with a hint that metals are always analyzed.
4. **Given** a duplicate or blank ticker is entered, **When** the user confirms,
   **Then** it is ignored (deduplicated / dropped) without error.

---

### User Story 2 - Generate a report on demand and open it (Priority: P1)

As the operator, I trigger a report run for the current watchlist (or a single
ticker) without waiting for the next hour, and I get a clickable link that opens a
self-contained HTML report in my browser.

**Why this priority**: Proves the whole analysis + render + link pipeline end to end
and is the manual fallback for the automation. Equal P1 because the hourly job is just
this action on a timer.

**Independent Test**: From the TUI, invoke "generate now"; within the run budget a
file appears at `reports/YYYY-MM-DD/HH-MM-<TICKER>.html`, the UI shows a clickable
link, and activating it opens the report in the default browser.

**Acceptance Scenarios**:

1. **Given** a non-empty watchlist, **When** the user triggers a run, **Then** one HTML
   report per instrument is written under `reports/<date>/`.
2. **Given** a report finished, **When** the user activates its link, **Then** the
   default browser opens the file (`file://` / OS open).
3. **Given** the Claude CLI is missing or errors for one ticker, **When** the run
   proceeds, **Then** the other tickers still produce reports and the failure is
   surfaced (status + an error report stub), not swallowed.
4. **Given** a report is generated, **When** it is opened, **Then** it renders a
   color-coded BUY / HOLD / SELL verdict, confidence %, the section breakdown, top-3
   reasons, and "what would change the recommendation".

---

### User Story 3 - Automatic hourly runs while the app is open (Priority: P2)

As the operator, while the TUI is running the analyzer fires automatically once per
hour, on the hour, for every watchlist instrument, writing reports without any manual
action. The most recent run's links are visible in the UI.

**Why this priority**: The headline ask, but it depends on US1+US2 existing. Built on
the same run path, just scheduled.

**Independent Test**: Set the interval short for the test, leave the app running across
two boundaries, and confirm two timestamped report sets are produced unattended.

**Acceptance Scenarios**:

1. **Given** the scheduler is enabled, **When** the top of an hour passes, **Then** a
   run starts automatically for the full watchlist.
2. **Given** a scheduled run is already in progress, **When** the next boundary fires,
   **Then** the runs do not overlap/stack (the new tick is skipped or queued, never
   concurrent for the same ticker).
3. **Given** the scheduler is toggled off in settings, **When** an hour boundary
   passes, **Then** no run starts.
4. **Given** the app was closed, **When** it is relaunched, **Then** scheduling resumes
   from the next boundary (no catch-up backfill of missed hours).

---

### User Story 4 - Reports browsable as a dated archive (Priority: P3)

As the operator, I browse past reports both in the TUI (a recent-reports list) and in a
browser via a generated `reports/index.html`, organized by date and time.

**Why this priority**: Quality-of-life. The reports exist and are openable without it;
this makes history navigable.

**Independent Test**: After several runs across two dates, open `reports/index.html`
and confirm every report is linked and grouped by date, newest first.

**Acceptance Scenarios**:

1. **Given** reports exist for multiple dates, **When** `index.html` is opened, **Then**
   reports are grouped by date folder, newest first, each a working link.
2. **Given** a new report is written, **When** the run completes, **Then** the index is
   regenerated to include it.

---

### User Story 5 - Analysis tests its assumptions, not asserts them (Priority: P2)

As the operator, the report does not blindly apply rules like "stronger USD is bad for
gold" — it treats each rule as a **hypothesis** and checks today's actual price action,
explicitly stating when the market is confirming or contradicting the assumption.

**Why this priority**: This is the qualitative core that makes the report trustworthy.
It rides on US2's pipeline but defines the prompt contract.

**Independent Test**: Inspect a generated report; every macro driver (USD, yields,
geopolitics, US session) carries an "assumption vs actual reaction" line, and the final
verdict cites real reactions, not theory.

**Acceptance Scenarios**:

1. **Given** any macro assumption in the framework, **When** the report is generated,
   **Then** the report states whether today's market confirms or contradicts it and
   weights the verdict toward observed price action.
2. **Given** a correlation is broken (e.g. USD down but gold also down), **When** the
   report renders, **Then** it flags the broken correlation and names the dominant
   alternative driver.
3. **Given** the current Swedish clock time, **When** the report renders, **Then** it
   states the Swedish session phase and how much weight to give Swedish vs US factors.

### Edge Cases

- **Claude CLI not installed / not on PATH** → run fails fast with a clear UI message and
  a written error-stub report; scheduler stays alive for the next hour.
- **No network / web tools blocked** → the report must state which data it could not
  retrieve rather than fabricate numbers.
- **Empty watchlist** → metals (Gold/Silver) are still analyzed; the run is never empty.
- **Run exceeds time budget** → the in-flight ticker is timed out and recorded as failed;
  remaining tickers continue.
- **Disk/permission failure writing `reports/`** → surfaced as an error, not silent.
- **Markdown-fenced output** → the pipeline must strip/guard so the saved file is valid
  standalone HTML, not a fenced code block.
- **Clock at a DST boundary** → Swedish session phase uses `Europe/Stockholm`, so phase
  labels stay correct across the shift.
- **Two app instances running** → both schedulers could fire; runs must be safe to write
  concurrently (timestamped + per-ticker filenames avoid collisions).

## Requirements *(mandatory)*

### Functional Requirements

**Watchlist & configuration**

- **FR-001**: System MUST let the user view, add, and remove report tickers from inside
  the running TUI.
- **FR-002**: System MUST always analyze Gold (`XAU`) and Silver (`XAG`); these MUST NOT
  be removable from the watchlist.
- **FR-003**: System MUST persist the report watchlist and report settings across
  restarts in the existing settings store, deduplicating and dropping blank entries.
- **FR-004**: System MUST expose a toggle to enable/disable automatic hourly runs, and a
  configurable interval (default: 1 hour, on the hour).

**Triggering**

- **FR-005**: System MUST automatically start a report run once per interval while the
  app is running, aligned to the top of the hour by default.
- **FR-006**: System MUST prevent overlapping runs for the same ticker; a boundary that
  arrives during an in-flight run MUST be skipped (no backfill of missed hours).
- **FR-007**: System MUST let the user trigger a run on demand for the whole watchlist or
  a single instrument, independent of the schedule.
- **FR-007a**: Within a single pass, System MUST analyze the watchlist instruments
  **concurrently** (one task per report), bounded by a configurable max-concurrency
  (default 3, `1` = sequential), so a full watchlist completes well inside the interval. A
  single instrument's failure MUST NOT cancel the others.
- **FR-008**: System MUST be runnable headlessly (one-shot, no TUI) for a single ticker
  or the full watchlist, so an external scheduler can drive it if desired.

**Analysis via Claude CLI**

- **FR-009**: System MUST invoke the Claude CLI (`claude`) in headless print mode to
  produce each report, granting it only the web/read tools needed to gather live data.
- **FR-010**: System MUST inject per-run context into the prompt: the instrument, the
  current `Europe/Stockholm` time, the derived Swedish session phase, the current date,
  and the inferred US-market state.
- **FR-011**: The analysis prompt MUST treat all macro assumptions as **hypotheses to
  validate against today's actual market reaction**, prioritizing observed price action
  over theory, and MUST flag broken correlations with the dominant alternative driver.
- **FR-012**: The analysis MUST cover, per instrument: Swedish session timing weighting,
  US-market state, US economic-news impact, USD (USD/SEK + DXY), gold/silver vs USD,
  bonds/yields, European indices, sector/capital flow, market regime, positioning &
  breadth, correlation validation, geopolitical risk, scenario probabilities (summing to
  100%), the next catalyst still ahead today, instrument-specific technical/fundamental
  read, and an explicit trade-timing assessment for the current clock.
- **FR-013**: The report MUST end with a fixed summary block: intraday and swing
  BUY/HOLD/SELL, confidence %, Swedish phase, US state, and per-driver
  Positive/Neutral/Negative impacts, top-3 reasons, and "what would change the
  recommendation".

**Output & linking**

- **FR-014**: System MUST save each report as a self-contained HTML file at
  `reports/<YYYY-MM-DD>/<HH-MM>[-<TICKER>].html` relative to the repository root, in the
  local `Europe/Stockholm` clock.
- **FR-015**: Saved files MUST be valid standalone HTML (inline CSS, no external assets,
  no markdown fences), with a color-coded verdict card.
- **FR-016**: System MUST present a clickable link to each finished report in the TUI and
  open it in the default browser when activated.
- **FR-017**: System MUST (re)generate a `reports/index.html` listing all reports grouped
  by date, newest first, after each run.
- **FR-018**: System MUST record per-run status (success/failure, duration, output path)
  and surface failures rather than silently dropping them.

### Key Entities

- **ReportTicker**: an instrument to analyze — symbol, display label, pinned flag (metals
  are pinned). The watchlist is the ordered set of these.
- **ReportSettings**: enabled flag, interval, watchlist tickers, allowed Claude tools,
  per-run timeout, output directory — persisted alongside existing `AppSettings`.
- **AnalysisPromptContext**: the per-run substitutions injected into the prompt template
  (ticker, Stockholm time, Swedish phase, date, US-market state).
- **ReportRun**: one execution — instrument, start/end time, status, duration, resulting
  file path, and any error.
- **AnalysisReport**: the rendered self-contained HTML artifact for one instrument at one
  timestamp, including the structured verdict.
- **ReportIndex**: the generated browse page aggregating all reports by date.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can add a ticker to the watchlist and produce a report for it in
  under 2 minutes from a running app, with zero file paths typed by hand.
- **SC-002**: While the app runs, an unattended report set is produced every interval
  with no missed or duplicated runs over an 8-hour window.
- **SC-003**: 100% of generated files open directly in a browser as valid HTML (no manual
  un-fencing, no broken layout, no external asset fetches).
- **SC-004**: Every report explicitly states, for each macro driver, whether today's
  market confirms or contradicts the assumption (0 reports that only assert theory).
- **SC-005**: A single-ticker headless run completes within its configured time budget
  (default ≤3 min) or is cleanly recorded as a timeout without blocking other tickers.
- **SC-006**: After multiple runs across ≥2 dates, `reports/index.html` links to 100% of
  produced reports, correctly grouped and ordered newest-first.

## Assumptions

- The `claude` CLI is installed, authenticated (subscription auth), and on `PATH`; no
  Anthropic API key is required (uses the existing CLI login).
- The machine has internet access during runs so the CLI's web tools can fetch live data.
- Reports are advisory/personal; this is **not** financial advice and produces no trades.
  It never auto-executes against the existing trade simulator.
- Scheduling only runs while the TUI (or the headless runner) is active; missed hours are
  not backfilled.
- `reports/` lives in the repository working tree and is git-ignored (artifacts, not
  source).
- Reuses the existing `Europe/Stockholm` helpers (`data/session.py`,
  `data/trading_hours.py`) for clock/phase logic rather than introducing a new TZ source.
- Metals are analyzed as spot `XAU`/`XAG`; the CLI maps them to whatever public symbols
  it finds live — consistent with the project's spot-price framing.
