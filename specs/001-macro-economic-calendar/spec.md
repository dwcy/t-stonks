# Feature Specification: Macro Economic Calendar + FX Rates

**Feature Branch**: `001-macro-economic-calendar`
**Created**: 2026-05-28
**Status**: Draft
**Input**: User description: "Macro economic data calendar in the TUI with time, in 3 sections (yesterday gray, today white, upcoming 5 days gray). Need ECB, Swedish (Riksbank), and FED events. Prefer EconDB if it can supply most of this. Also add CAD→SEK and USD→SEK currency rates polled every 10 minutes. Also a small Brent Oil quote — no chart, just arrow + change + change% (e.g. `▼ -1.54% (-68.46)`)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - See today's macro events at a glance (Priority: P1)

While watching live gold/silver prices, the user can see a side panel listing today's scheduled
macro-economic releases and central-bank events from the FED, ECB, and Riksbank, each with the
local time it is scheduled. Today's events are rendered with a bright white emphasis so they are
immediately distinguishable from past or future days. This lets the user correlate price moves
with the macro events that drive them in real time.

**Why this priority**: The whole point of adding a calendar to a real-time precious-metals TUI is
to give context for *current* price movement. Yesterday and upcoming days are useful background
but the live trading day is what the user reacts to. Today-only is a usable MVP.

**Independent Test**: Launch the TUI on any weekday during European/US trading hours. The
calendar section must show ≥1 event (or an explicit "no scheduled events today" line) with each
event labelled by source (FED / ECB / RIKSBANK), local time, and event title, styled brighter
than yesterday/upcoming entries.

**Acceptance Scenarios**:

1. **Given** the TUI is running on a day with scheduled FED/ECB/Riksbank releases, **When** the
   user looks at the calendar panel, **Then** today's events appear under a clearly-labelled
   "Today" section in white/bright text with local time, source tag, and title.
2. **Given** no events are scheduled for today, **When** the user looks at the calendar panel,
   **Then** the "Today" section renders a single muted "no scheduled events" line so the user
   knows the data loaded successfully.
3. **Given** an event's scheduled time has already passed today, **When** the user looks at the
   calendar, **Then** the event still appears in the "Today" section (it is not promoted to
   "Yesterday") but is visually marked as already-occurred.

---

### User Story 2 - Show yesterday for context (Priority: P2)

The calendar shows yesterday's events in a "Yesterday" section above today, rendered in muted
gray. The user uses this to retrospectively read the chart: a price gap or spike on the
overnight bar is explained by a release that happened the day before.

**Why this priority**: One-day lookback is the highest-value retrospective window. Anything older
than that the user can find on a web calendar; the value of the TUI is the *immediately adjacent*
context.

**Independent Test**: Launch the TUI; the calendar must show a "Yesterday" header above "Today".
If yesterday had scheduled events, they appear under it in muted gray with the same fields as
today. If yesterday had none, an explicit muted "no events" line appears.

**Acceptance Scenarios**:

1. **Given** yesterday had a FED FOMC statement at 19:00 UTC, **When** the user opens the TUI
   today, **Then** that event appears under a "Yesterday" header rendered in dim gray, with the
   scheduled time as it was originally announced.
2. **Given** yesterday was a weekend or holiday with no macro releases, **When** the user opens
   the TUI, **Then** the "Yesterday" section still exists with a muted placeholder line.

---

### User Story 3 - Look ahead at the next five days (Priority: P2)

Below today, the calendar shows the next five calendar days (not five business days), each as a
dated sub-header in dim gray with its events listed under it. The user scans this to prepare for
upcoming volatility — e.g. a Riksbank rate decision two days out, an ECB press conference
Thursday, US CPI on Friday.

**Why this priority**: Forward-looking events are essential for planning, but secondary to the
live-context use case. Five days covers the typical macro week without overflowing the panel.

**Independent Test**: Launch the TUI; the calendar must show exactly five day-headers after
today, each labelled with the weekday + date. At least one of those five days, on a typical
week, must contain a known event such as ECB Lagarde speech, FED Fed minutes, or Riksbank rate
decision.

**Acceptance Scenarios**:

1. **Given** today is Monday, **When** the user opens the TUI, **Then** the calendar lists five
   dated sub-sections for Tue, Wed, Thu, Fri, Sat — each in dim gray — with their events.
2. **Given** an upcoming day has no scheduled releases, **When** the user reads the calendar,
   **Then** that day's sub-header still appears with a muted "no events" line, so the day
   structure is visually consistent.
3. **Given** the user keeps the TUI open past midnight, **When** the date rolls over, **Then**
   the calendar re-segments so the old "today" becomes "yesterday" and a new day enters the
   five-day window without requiring a restart.

---

---

### User Story 4 - See CAD→SEK and USD→SEK rates live (Priority: P2)

The TUI shows two currency-pair tiles — **USD/SEK** and **CAD/SEK** — with the latest rate,
absolute change vs. the previous day's close, and percentage change. The user reads these to
sanity-check whether a move in the dollar gold price is "real" gold action or just SEK
weakness/strength, and to track CAD exposure (the user holds CAD-denominated assets).

**Why this priority**: Same user, same screen, same kind of data (a polled number with a
reference close). Cheap to add and directly complementary to the gold/silver USD prices
already displayed.

**Independent Test**: Launch the TUI. Within ~15 s, the two FX tiles must display non-placeholder
values for USD/SEK and CAD/SEK, with change and change-% rendered with the same color
convention as the metals panels (green up, red down). The values must update at least once per
10 minutes of uptime.

**Acceptance Scenarios**:

1. **Given** the TUI is running on a weekday during FX market hours, **When** the user looks at
   the FX section, **Then** USD/SEK and CAD/SEK both show a recent rate (timestamp ≤10 min old)
   with change vs. yesterday's close.
2. **Given** the FX upstream returns an error, **When** the user looks at the FX section,
   **Then** the last-known values remain visible with a "stale since HH:MM" marker, and the
   live metals feed is unaffected.
3. **Given** the FX feed has not yet returned its first response, **When** the TUI has just
   started, **Then** the FX tiles show a muted "loading…" placeholder rather than crashing or
   showing 0.0000.

---

### User Story 5 - Quick-glance Brent crude oil quote (Priority: P3)

A small inline quote (no chart) shows the current Brent crude oil spot price with a direction
arrow, absolute change, and percentage change vs. previous close. Format example:

```
BRENT  68.46  ▼ -1.54% (-1.07)
```

Used by the user to read the broader commodity-complex tone alongside gold/silver.

**Why this priority**: Same data shape as FX — one polled number with a reference close — but
displayed compactly, no chart. Reuses whatever quote service is added for FX.

**Independent Test**: Launch the TUI. Within ~15 s a Brent tile renders with a non-placeholder
price, a `▲` or `▼` arrow colored green/red, the percent change, and the absolute change in
parentheses. The value refreshes at least once per 10 minutes.

**Acceptance Scenarios**:

1. **Given** the TUI is running on a weekday during oil-market hours, **When** the user looks
   at the Brent tile, **Then** it displays the rate, the direction arrow, change-%, and
   absolute change as shown in the format example.
2. **Given** the upstream returns an error, **When** the user looks at the Brent tile,
   **Then** the last-known values remain visible with a "stale since HH:MM" marker.

---

### Edge Cases

- **Network unreachable / API returns 5xx**: calendar panel must render in a degraded state
  (e.g. a one-line "calendar unavailable — retrying in N s" in dim red), never crash the TUI or
  block the live price feed.
- **API rate limits**: the calendar refresh cadence must respect the upstream limit and not
  starve the live price worker.
- **Mixed timezones**: FED releases are typically published in US/Eastern, ECB in CET/CEST,
  Riksbank in CET/CEST. The "today / yesterday / upcoming" segmentation must use a single
  consistent reference timezone (see Assumptions) so a US release at 14:30 ET doesn't appear
  under "tomorrow" in Stockholm.
- **DST transitions** in the user's reference timezone must not double-render or skip an event.
- **All-day events** (e.g. "Eurogroup meeting") have no time-of-day; render with `--:--` or an
  equivalent placeholder rather than a fabricated 00:00.
- **Event time revisions** between fetches (rare but happens with FED): the displayed event must
  reflect the latest fetch, not a stale earlier value.
- **Empty upstream response** (parser succeeds but list is empty for the full 7-day window):
  treat as "unavailable" rather than silently showing seven empty days.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The TUI MUST display a macro-economic calendar panel alongside the existing gold
  and silver panels without reducing the live price feed's update cadence or readability.
- **FR-002**: The calendar MUST be segmented into three vertically stacked sections in this
  order: **Yesterday**, **Today**, **Upcoming (next 5 days)**.
- **FR-003**: The **Today** section MUST be rendered in a high-contrast bright/white style; the
  **Yesterday** and **Upcoming** sections MUST be rendered in a muted gray style.
- **FR-004**: Each event entry MUST display, at minimum: scheduled local time, source tag
  (`FED`, `ECB`, `RIKSBANK`), and event title. Forecast / previous values MAY be shown if the
  upstream provides them, but are not required.
- **FR-005**: The calendar MUST include events from the **US Federal Reserve**, the **European
  Central Bank**, and **Sveriges Riksbank**. Other central banks or releases MAY appear if a
  unified upstream returns them, but must not crowd out the three required sources.
- **FR-006**: The calendar MUST source its data from a free, no-API-key (or free-tier) public
  endpoint, preferred unified provider being [NEEDS CLARIFICATION: confirm EconDB or fallback to
  per-source endpoints — see research.md].
- **FR-007**: The calendar MUST refresh its event list periodically without user interaction; the
  refresh interval MUST be slow enough not to hit upstream rate limits (suggested ≥10 min, since
  event lists change far more slowly than prices). Live event status (e.g. "actual value
  released") MAY refresh faster if the chosen provider supports it cheaply.
- **FR-008**: The "upcoming 5 days" window MUST cover the **next 5 calendar days** after today,
  inclusive of weekends, each rendered as its own dated sub-section with weekday + ISO date.
- **FR-009**: On data fetch failure, the calendar panel MUST degrade gracefully: keep showing
  the last successfully fetched data with a visible "stale since HH:MM" marker, OR if no prior
  data exists, show "calendar unavailable" plus the retry countdown. Failure MUST NOT crash the
  app or block the price feed.
- **FR-010**: The date rollover at midnight MUST automatically re-segment events
  (today→yesterday, tomorrow→today, etc.) without restarting the TUI.
- **FR-011**: All event times MUST be converted to a single consistent display timezone (see
  Assumptions) before segmentation and rendering, so the "today" bucket has the same boundaries
  as the user's perceived day.
- **FR-012**: Events already past their scheduled time on the current day MUST remain in the
  "Today" section but MUST be visually distinguished (e.g. dimmed or struck-through) from
  upcoming today-events.
- **FR-013**: The keybinding scheme MUST gain a "refresh calendar" action (suggested `c` or
  similar) that triggers an out-of-band fetch on demand.
- **FR-014**: The TUI MUST display two FX currency-pair tiles: **USD/SEK** and **CAD/SEK**.
  Each tile MUST show the current rate, the absolute change vs. the previous day's close, and
  the change as a percentage, using the same color convention as the existing metals panels.
- **FR-015**: The FX rates MUST be fetched via active polling on a fixed cadence of
  approximately **10 minutes** (not faster — central-bank reference and most free FX feeds
  publish at most every few minutes anyway).
- **FR-016**: The FX source MUST be a free, no-API-key public endpoint
  [NEEDS CLARIFICATION: confirm provider — candidates include exchangerate.host, ECB
  EUR-cross-rates with derived USD/SEK and CAD/SEK, frankfurter.app, Bank of Canada Valet, see
  research.md].
- **FR-017**: FX fetch failure MUST degrade gracefully (keep last value with a "stale since
  HH:MM" marker) and MUST NOT crash the TUI or block the price/calendar feeds.
- **FR-018**: The FX tiles MUST share the same reactive-widget pattern, async-worker pattern,
  and Pydantic-validation discipline used by the existing metals panels — no new architectural
  primitives.
- **FR-019**: The TUI MUST display a compact **Brent crude oil** quote tile (no chart) showing
  current price, direction arrow (`▲` / `▼` / `▬`), absolute change, and change percent vs.
  previous close. Suggested format: `BRENT  <price>  ▼ -X.XX% (-Y.YY)`.
- **FR-020**: Brent quote MUST poll on the same ~10-minute cadence as the FX tiles and use a
  free, no-API-key source [NEEDS CLARIFICATION: confirm provider — candidates include
  yfinance `BZ=F` (already a project dependency), Stooq CSV, EIA open data, see research.md].
- **FR-021**: Brent fetch failure MUST degrade with last-known value + "stale" marker, never
  crash the TUI, never block other feeds.

### Key Entities

- **CalendarEvent**: a scheduled macro-economic release or central-bank communication. Carries:
  `source` (FED / ECB / RIKSBANK / other), `title` (human-readable label),
  `scheduled_time` (timezone-aware datetime, may be date-only for all-day events), `importance`
  (high/medium/low, if upstream provides it; otherwise inferred or omitted), optionally
  `forecast`, `previous`, `actual` values for releases with numeric data, and a `status`
  (scheduled / released / cancelled).
- **CalendarDay**: a logical grouping of zero or more events under one date in the user's
  display timezone, plus a `bucket` label (`yesterday`, `today`, or `upcoming`) used by the
  rendering layer to choose its styling.
- **CalendarSnapshot**: the result of one upstream fetch — the seven-day window of CalendarDays
  plus the fetch timestamp and a `status` (ok / stale / unavailable) used by the panel to render
  staleness indicators.
- **FxRate**: a single foreign-exchange quote. Carries `pair` (e.g. `USDSEK`, `CADSEK`),
  `rate` (float), `previous_close` (float, anchor for change/%), `time` (UTC datetime),
  and the derived `change` / `change_percent`.
- **CommodityQuote**: a polled non-charted commodity price. Carries `symbol` (e.g. `BRENT`),
  `price` (float), `previous_close` (float), `time` (UTC datetime), and the derived `change` /
  `change_percent`. Same shape as `FxRate` — likely the same model with a different label,
  evaluated in research.md.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: From a cold start, the calendar panel shows real data (not the loading placeholder)
  within **5 seconds** on a healthy network.
- **SC-002**: Users can identify today's next upcoming macro event in **under 2 seconds** of
  visual scan — i.e. the "Today" section's contrast against gray Yesterday/Upcoming sections
  makes "what's next today" pre-attentive.
- **SC-003**: The calendar refresh cycle generates **≤ 1 upstream request per source per
  10 minutes** in steady state, well inside published rate limits of any of the candidate APIs.
- **SC-004**: Upstream calendar fetch failures cause **0 crashes** of the TUI and **0**
  interruptions to the live price feed; the live price feed continues ticking at its normal
  cadence regardless of calendar state.
- **SC-005**: A keyboard-only user can refresh and read the calendar without touching the mouse
  — refresh shortcut MUST be present and documented in the footer.
- **SC-006**: On a 80-column terminal, the calendar panel renders all three sections readably,
  with each event entry on a single line (truncating the title with an ellipsis if needed) —
  not requiring scroll for the typical 0-5 events per day.
- **SC-007**: USD/SEK and CAD/SEK tiles display first real values within **15 seconds** of cold
  start and refresh **at least every 10 minutes** thereafter on a healthy network.
- **SC-008**: Steady-state FX traffic is **≤ 1 request per pair per 10 minutes** (≤ 12 req/h
  total for both pairs), comfortably below any free-tier limit on the candidate providers.
- **SC-009**: Brent tile shows a real value within **15 seconds** of cold start and refreshes
  at least every **10 minutes** thereafter; failures degrade gracefully without affecting other
  feeds.

## Assumptions

- **Display timezone is Europe/Stockholm.** This matches the existing chart's x-axis origin and
  the user's locale. All upstream UTC/ET timestamps are converted to Europe/Stockholm before
  bucket assignment.
- **Free public endpoints are sufficient.** The user explicitly asked for "free" sources and
  preferred an EconDB unified backend. Paid macro-calendar services (Investing.com,
  FXStreet, TradingEconomics premium) are out of scope.
- **Static schedule data is acceptable.** Real-time "actual value released" tickers are nice to
  have but not required by FR-004; the MVP is the *schedule* with title + time.
- **No persistence layer.** Per the existing project rules ("no backend, REST server, or
  persistence layer"), the calendar lives in memory inside the TUI process and is refetched on
  startup.
- **No new GUI framework.** Calendar must be rendered with Textual widgets and follow the
  existing reactive widget pattern (`reactive` attrs, async I/O in workers).
- **FX quotes are reference rates, not tradable bid/ask.** ECB / Bank of Canada / similar free
  feeds publish mid-market reference rates; that is what the user wants to see, not a live
  inter-bank tradable spread.
- **No deduplication across sources required.** The three required sources publish disjoint
  events — a FED FOMC and an ECB rate decision are distinct events with no overlap risk. If a
  unified provider (EconDB) returns the same event twice, the implementation MAY dedupe but the
  spec does not require it.
- **English event titles are acceptable.** No localization required.
