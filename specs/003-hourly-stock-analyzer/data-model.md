# Phase 1 Data Model: Hourly Stock-Analysis Reports

All types live under `src/goldsilver/reports/` except `ReportSettings`, which nests into
the existing `AppSettings` (`src/goldsilver/data/settings.py`). Dataclasses with `slots`
+ `__post_init__` validation are used for config (matching `SimulatorSettings`); Pydantic
v2 is used for any payload that crosses the Claude-CLI boundary (per repo CLAUDE.md).

---

## ReportSettings  *(dataclass, nested in `AppSettings`)*

Persisted config controlling the engine.

| Field | Type | Default | Validation |
|---|---|---|---|
| `enabled` | `bool` | `False` | coerced to bool; scheduler off until opted in |
| `interval_minutes` | `int` | `60` | clamp to `[15, 1440]`; invalid → 60 |
| `report_tickers` | `list[str]` | `[]` | strip, dedupe, drop blanks (same cleaner as `stock_tickers`); **stocks only** |
| `timeout_seconds` | `int` | `180` | clamp to `[30, 900]`; invalid → 180 |
| `allowed_tools` | `list[str]` | `["WebSearch", "WebFetch", "Read"]` | non-empty subset of a known tool allowlist; invalid entries dropped |
| `out_dir` | `str` | `"reports"` | non-empty; resolved relative to repo root |

**Notes**: Gold/Silver are **not** stored here — they are pinned constants
(`PINNED_METALS = ("XAU", "XAG")`) prepended in the engine, so they can never be removed
(FR-002). `report_tickers` is independent of the existing `stock_tickers` (chart tiles).

---

## ReportTicker  *(dataclass / value object)*

One instrument to analyze.

| Field | Type | Notes |
|---|---|---|
| `symbol` | `str` | canonical symbol, e.g. `XAU`, `LUG.ST`, `NVDA` |
| `label` | `str` | display name, e.g. "Gold", "Lundin Gold (Sthlm)" |
| `pinned` | `bool` | `True` for metals; pinned rows cannot be removed in the UI |
| `kind` | `Literal["metal", "stock"]` | drives prompt framing (spot metal vs equity) |

**Derivation**: `safe_name` property → symbol uppercased with `/ . space :` → `-`
(used in filenames, see report-file contract).

The **effective watchlist** for a run = `[ReportTicker(m, pinned=True) for m in PINNED_METALS] + report_tickers`.

---

## AnalysisPromptContext  *(dataclass — substituted into the template)*

The per-run values injected into `analysis_prompt.md`.

| Field | Type | Source |
|---|---|---|
| `ticker` | `str` | the instrument symbol |
| `ticker_label` | `str` | display label |
| `ticker_kind` | `Literal["metal", "stock"]` | metal vs stock framing |
| `stockholm_time` | `str` | `now(STOCKHOLM)` formatted `YYYY-MM-DD HH:MM` |
| `date` | `str` | `YYYY-MM-DD` (Stockholm) |
| `swedish_phase` | `SwedishPhase` | from `phase.py` |
| `us_market_state` | `USMarketState` | from `phase.py` |

Placeholders in the template: `{TICKER}`, `{TICKER_LABEL}`, `{TICKER_KIND}`,
`{STOCKHOLM_TIME}`, `{DATE}`, `{SWEDISH_PHASE}`, `{US_MARKET_STATE}` (exact set is the
analysis-prompt contract). Substitution is literal `str.replace` over a known key set
(no `.format()` — the template contains literal `{` in CSS/JSON examples).

---

## SwedishPhase / USMarketState  *(enums, `str`-valued)*

```
SwedishPhase  = MORNING_STRENGTH | MIDDAY_WEAKNESS | TREND_FOLLOWING
              | US_INFLUENCE | US_DOMINATED | CLOSED
USMarketState = CLOSED | PRE_MARKET | OPENING | OPEN | NEAR_CLOSE
```

Derivation rules and DST handling: see research D4. Pure functions
`swedish_phase(dt) -> SwedishPhase` and `us_market_state(dt) -> USMarketState` in
`phase.py`, both taking a `Europe/Stockholm`-aware datetime.

---

## ReportStatus  *(enum, `str`-valued)*

```
PENDING | RUNNING | SUCCESS | MALFORMED | TIMEOUT | CLI_MISSING | ERROR
```

- `MALFORMED` — CLI returned output that failed the HTML prefix guard (D5).
- `CLI_MISSING` — `claude` not found on PATH.
- `TIMEOUT` — exceeded `timeout_seconds`.
- `ERROR` — non-zero exit / unexpected exception (message captured).

---

## ReportRun  *(Pydantic model — the run record + sidecar JSON)*

Serialized to `<HH-MM>-<TICKER>.json` next to each report.

| Field | Type | Notes |
|---|---|---|
| `ticker` | `str` | symbol |
| `label` | `str` | display label |
| `started_at` | `datetime` | Stockholm-aware |
| `finished_at` | `datetime \| None` | set on completion |
| `duration_seconds` | `float \| None` | wall-clock |
| `status` | `ReportStatus` | terminal state |
| `html_path` | `Path \| None` | relative to repo root |
| `verdict` | `Verdict \| None` | parsed from the report's `<!-- VERDICT: … -->` header |
| `error` | `str \| None` | message when failed |

---

## Verdict  *(Pydantic model — the structured recommendation)*

Mirrors the prompt's fixed final-summary block; emitted by Claude as a JSON comment on
line 1 of the HTML (`<!-- VERDICT: {…} -->`) and rendered visually in the body.

| Field | Type | Allowed |
|---|---|---|
| `intraday` | `Literal["BUY","HOLD","SELL"]` | |
| `swing` | `Literal["BUY","HOLD","SELL"]` | 1–4 week |
| `confidence` | `int` | 0–100 |
| `swedish_phase` | `str` | echoed phase label |
| `us_state` | `str` | echoed US state |
| `usd_impact` | `Literal["Positive","Neutral","Negative"]` | |
| `gold_impact` | `Literal["Positive","Neutral","Negative"]` | |
| `news_impact` | `Literal["Positive","Neutral","Negative"]` | |
| `geopolitical_impact` | `Literal["Positive","Neutral","Negative"]` | |
| `top_reasons` | `list[str]` | exactly 3 |
| `what_would_change` | `list[str]` | ≥1 |

Parsing is tolerant: if the comment is missing/invalid, `verdict=None`, `status` stays
`SUCCESS` (the HTML is still valid), and the index shows "—" for verdict.

---

## ReportIndex  *(generated artifact, not a stored model)*

`reports/index.html`, rebuilt after every run from the set of sidecar JSONs found under
`reports/*/*.json`: grouped by date `<h2>` (newest first), each entry a relative link
with time, ticker, color-coded verdict, and confidence.

---

## Relationships

```
AppSettings 1───1 ReportSettings
ReportSettings ──derives──> effective watchlist: [ReportTicker(metal, pinned)] + report_tickers
ReportScheduler ──每 interval──> ReportService.run_all(watchlist)
ReportService ──per ticker──> AnalysisPromptContext ──prompt_builder──> prompt string
                          └──> claude_runner ──> raw HTML ──> html_writer ──> AnalysisReport(.html) + ReportRun(.json)
html_writer ──aggregates all .json──> ReportIndex (index.html)
ReportRun.verdict 0/1 Verdict
```

## State transitions (ReportRun)

```
PENDING → RUNNING → SUCCESS                (valid HTML written, verdict parsed or None)
                 ├→ MALFORMED              (output failed HTML guard; error shell written)
                 ├→ TIMEOUT                (killed after timeout_seconds)
                 ├→ CLI_MISSING            (claude not on PATH; no process started)
                 └→ ERROR                  (non-zero exit / exception)
```
A boundary tick that arrives while a run is `RUNNING` for the same ticker is skipped
(FR-006); it does not create a second `ReportRun`.
