# Phase 0 Research: Macro Calendar + FX + Brent

Resolves the **NEEDS CLARIFICATION** markers from `spec.md` (calendar provider, FX provider,
Brent provider) and the Technical Context entries in `plan.md`.

---

## R1 — Calendar provider strategy

### Decision

**Hybrid, not unified.** Use:

- **US releases (CPI, NFP, PPI, retail sales, etc.)** → **FRED API**
  `https://api.stlouisfed.org/fred/releases/dates` with a free API key
  (`api_key=<key>&file_type=json&include_release_dates_with_no_data=true`).
- **FOMC meetings (rate decisions, minutes, press conferences)** → **static yearly schedule**
  embedded in the codebase. Refresh once a year from
  `https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm`.
- **ECB Governing Council meetings + press conferences** → **static yearly schedule**, refreshed
  yearly from `https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html`.
- **Riksbank Executive Board rate decisions + monetary policy reports** → **static yearly
  schedule**, refreshed yearly from Riksbank's published calendar.

### Rationale

- The user asked for free, no-key public APIs and suggested **EconDB** as a unified backend.
  Investigation shows EconDB only exposes **time-series** endpoints (
  `https://www.econdb.com/api/`, `https://developers.econdb.com/`) — there is no event /
  calendar / scheduled-release endpoint. It cannot drive this feature.
- **FRED's `releases/dates`** *does* return upcoming scheduled release dates for hundreds of US
  releases. Since FRED v2 (Nov 2025) an API key is mandatory, but keys are free, take seconds
  to obtain, and only one is needed for the whole feature. Treat the key as an opt-in: read
  from `GOLDSILVER_FRED_KEY` env var; if missing, the US-releases sub-source silently degrades
  to FOMC-only.
- The ECB has **no public JSON / iCal / RSS feed** for its press calendar — confirmed by direct
  fetch of `https://www.ecb.europa.eu/press/calendars/weekly/html/index.en.html`. The ECB *does*
  publish an indicative annual calendar once a year as a press release, and only 8 Governing
  Council meetings happen per year. Static data is the right granularity.
- Same logic applies to the Riksbank Executive Board — ~8 meetings/year, fixed annual schedule.
- Hardcoding a 12-month rolling table costs ~30 entries per year per source — trivial to
  maintain and avoids one-off scrapers that rot when the upstream HTML changes.

### Alternatives considered

- **EconDB unified backend** — rejected. No calendar endpoint, only time series.
- **Trading Economics free tier** — rejected. Calendar API is behind a paid plan; the public
  HTML is rate-limited and ToS-restricted.
- **`fin2dev`, `financeflowapi`, `financialmodelingprep` calendar APIs** — rejected. Paid /
  trial-only, requires registration, future-cost risk.
- **Generic free RSS scrape (federalreserve.gov/feeds/press_monetary.xml etc.)** — rejected for
  the FED calendar use case: those feeds publish events as they happen, not the *upcoming
  schedule*. Useful only for "fired today" notifications, not a forward 5-day view.
- **iCal scrape of ECB / Riksbank** — rejected for MVP. No published iCal endpoints exist;
  scraping HTML calendars is fragile.

### Implementation note

- Static schedules live in `src/goldsilver/data/calendar_static.py` as Pydantic models, one
  list per source per year (`FOMC_2026: list[StaticEvent]`, `ECB_2026: list[StaticEvent]`,
  `RIKSBANK_2026: list[StaticEvent]`).
- A trivial yearly-refresh checklist goes in CLAUDE.md (or a top-level `CALENDAR.md`).
- The FRED puller is async (`httpx.AsyncClient`), 10-minute cadence, gracefully no-ops if
  `GOLDSILVER_FRED_KEY` is unset.

---

## R2 — FX provider (USD/SEK and CAD/SEK)

### Decision

**Primary: Riksbank SWEA REST API.**

- Base URL: `https://api.riksbank.se/swea/v1/`
- Latest USD/SEK: `GET /Observations/Latest/sekusdpmi`
- Latest CAD/SEK: `GET /Observations/Latest/sekcadpmi`
- Previous-close anchor: `GET /Observations/{seriesId}?from=<YYYY-MM-DD>&to=<YYYY-MM-DD>` for
  the prior business day, or use the second-most-recent value.
- Auth: **none required**. Public open API.
- Rate limit: not formally published; the Riksbank docs treat it as a courtesy-use public
  service. 10-min polling per pair is well within reason.

**Fallback: Frankfurter** — `https://api.frankfurter.dev/v2/rates?base=USD&quotes=SEK,CAD`.
No key, no monthly cap, ECB-sourced daily rates. Used only when Riksbank returns an error
twice in a row.

### Rationale

- Riksbank publishes **SEK-per-foreign-currency** reference rates daily for ~40 currencies
  including USD and CAD. These are the rates Swedish users see in news / financial press —
  semantically the right anchor for a Swedish-locale TUI.
- Series IDs `SEKUSDPMI` and `SEKCADPMI` deliver exactly the two pairs requested.
- Free and keyless — fully meets the spec's free-API constraint without an env var.
- Frankfurter as fallback covers the case where the Riksbank API is briefly unreachable; it's
  also keyless and free with no daily cap.

### Quote convention (important, easy to invert)

Per the Riksbank's published convention from **2023-11-27** onward, exchange-rate series are
quoted as **SEK per 1 unit of the foreign currency**. So `sekusdpmi ≈ 10.5` means
"1 USD = 10.5 SEK", which is what the user expects to see as "USD/SEK 10.50". No inversion
required.

Validation guard: if the parsed value ever drops below `1.0`, treat as malformed and discard
(the rate has historically never been < 1 SEK per USD or per CAD).

### Alternatives considered

- **exchangerate.host** — current docs mention an "access key" parameter for some endpoints;
  uncertain free-tier guarantee. Rejected as primary, available as a tertiary fallback if
  needed later.
- **ECB Statistical Data Warehouse** — has EUR-cross rates only; USD/SEK and CAD/SEK would
  have to be derived via EUR. More moving parts. Rejected.
- **yfinance `SEK=X`, `CADSEK=X`** — yfinance is already a project dep, but it depends on
  Yahoo's unstable scrape interface; we already use it for chart-only historical data where
  occasional flakiness is tolerable. The FX tiles refresh every 10 min and are user-facing
  numbers — we want a stabler primary source.

---

## R3 — Brent crude oil quote

### Decision

**Use yfinance with symbol `BZ=F`** (Brent crude futures front-month, ICE).

- Already an installed dependency (no new package added).
- 10-min polling via the existing `fetch_history`-style async-to-thread wrapper.
- Pull a 2-day 1-day bar to get current close + previous close, derive change and %.

### Rationale

- The user wants *no chart, just an arrow + change + %* — a single price + reference close is
  all we need. yfinance's daily history endpoint is fine for that resolution; intra-day
  precision is overkill for a 10-min refresh anyway.
- Avoids adding a third upstream provider just for one number.
- If yfinance proves flaky in production, swap-out target is **Stooq CSV**
  (`https://stooq.com/q/d/l/?s=cl.f&i=d` for WTI; Brent equivalent `bz.f`) — also free, no key.

### Alternatives considered

- **EIA open data** — has Brent spot but lags ≥1 day; not suitable for "live-ish" tile.
- **OilpriceAPI / commodities-api** — paid tiers, rejected.
- **Investing.com scrape** — ToS issues, rejected.

---

## R4 — Display timezone and bucketing

### Decision

**Europe/Stockholm** for all three calendar buckets and FX/Brent timestamps.

### Rationale

- Matches the existing chart's x-axis origin (`stockholm_midnight_utc()` in `data/session.py`).
- Matches the user's locale.
- Bucket assignment:
  - `yesterday` = events whose `scheduled_time.astimezone(STK)` falls on `today_STK - 1 day`.
  - `today` = events whose `scheduled_time.astimezone(STK)` falls on `today_STK`.
  - `upcoming` = events in the next 5 calendar days after `today_STK`.
- The single conversion eliminates the cross-timezone "appears under tomorrow" footgun.

### Alternatives considered

- Per-event source timezone (US Eastern for FED, CET for ECB/Riksbank) — rejected. Inconsistent
  bucketing and confusing UX.
- UTC — rejected. Splits the user's perceived day at 02:00 / 01:00 local depending on DST.

---

## R5 — Refresh cadence and rate-limit budget

### Decision

| Source | Cadence | Steady-state requests / hour |
|---|---|---|
| FRED `releases/dates` (calendar, US releases) | 10 min | 6 |
| Static yearly schedules (FOMC / ECB / Riksbank events) | n/a (in-memory) | 0 |
| Riksbank SWEA `Observations/Latest/{series}` (USD/SEK) | 10 min | 6 |
| Riksbank SWEA `Observations/Latest/{series}` (CAD/SEK) | 10 min | 6 |
| Riksbank SWEA `Observations/{series}` previous-close (one pull per pair per day) | 1/day | 0.08 |
| yfinance `BZ=F` (Brent) | 10 min | 6 |
| **Total per hour, all upstreams combined** | | **~24** |

### Rationale

- Spec FR-007 + FR-015 + FR-020 already mandate ≥10-minute cadence on all polled quote /
  calendar sources. Holding everything to the same heartbeat simplifies the scheduler.
- A single shared 10-minute coroutine in `MetalsService` (or a sibling `MacroService`) fans
  out to all four pullers in parallel each tick.

### Alternatives considered

- 5-minute cadence on FX — rejected; SEK reference rates only refresh daily on Riksbank, so
  faster polling buys nothing and just doubles the request count.
- 1-hour cadence on calendar — acceptable, but 10 min keeps the "fetched at HH:MM" footer
  feeling fresh and matches the user's explicit instruction.

---

## R6 — Failure isolation

### Decision

**Each upstream lives behind its own async worker** with its own retry/backoff state. None of
the workers shares an `httpx.AsyncClient` with the live `goldprice.org` poller. A failed FRED
fetch must not pause the price feed; a failed Riksbank fetch must not pause Brent; etc.

### Rationale

- Matches the existing pattern in `data/service.py` where the Avanza refresh runs in its own
  task alongside the goldprice.org polling loop. Extend the same model for each new upstream.
- Allows partial-functionality degradation that matches FR-009 / FR-017 / FR-021.

### Alternatives considered

- One big sequential 10-min loop — rejected. A single hang on FRED would freeze FX and Brent
  too.

---

## Open items

- **Static schedule maintenance**: the FOMC / ECB / Riksbank 2026 lists need to be refreshed
  in late 2026 with the 2027 calendars when they publish (usually Q3 of the preceding year).
  Track via a one-line entry in `CLAUDE.md` under a `## Yearly maintenance` heading.
- **FRED key onboarding**: `quickstart.md` will explain how to obtain a free FRED key and set
  `GOLDSILVER_FRED_KEY`. Without it, the US-releases column degrades gracefully to "only
  FOMC events", which is still informative.
