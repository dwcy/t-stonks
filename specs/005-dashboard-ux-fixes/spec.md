# Feature Specification: Dashboard UX & Data-Quality Fixes

**Feature Branch**: `005-dashboard-ux-fixes`
**Created**: 2026-07-09
**Status**: Draft
**Input**: User description: "we need varios fixes... 1. add a description on the slope BB roc si mci z and what they mean when I press on them (hidden click) and also give a sort order on prio and why the one is worth more than the other. 2. the press tv feed date is wrong always, and always shown as latest when I start up the app... make sure the date and time is valid. and Keep the news in a log. 3. the news feed to the right add a click to read more that goes to the link. The macro calendar when the time has passed by 1 minute trigger auto fetch with a spinner shown. change 4. Au and dxy to readable name 5. on the gold and silver report name it gold or silver not the short name. 6. Also add Report generation on copper and oil." Follow-up addition: "to the specification I want you to add räntan för USA och Sverige. 2. Lägg till Tyska, Franska, Brittiska, Japanska börsen också." (add USA and Sweden interest rates; add German, French, British, Japanese stock exchanges too.) Second follow-up addition: "when I press the mini chart, open up a modal with that chart full detail chart like the gold and silver chart. and bellow that chart and a 40 last days like this [arrow up percentage, or arrow down percentage]" Third follow-up addition: "the upcomming reports and daily reports from my subscribed minicharts (selected) should also be shown. And Not only reports but when they give money and how much. this info should also be in the detailed large modal when pressing the mini chart."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Trustworthy news timestamps and a news history (Priority: P1)

As a user watching the news feed, I need every headline's date/time to reflect when it was actually published — not the moment the app happened to refresh — and I need a way to look back at news I've already seen, so I can trust the feed enough to act on it and never lose a headline that scrolled off the panel.

**Why this priority**: This is a correctness bug that actively misleads the user (stale news masquerading as breaking news) every time the app starts. Trust in the data feed is the foundation the rest of the app depends on, so this is fixed first.

**Independent Test**: Start the app fresh and confirm no headline shows a timestamp equal to "now" unless it was genuinely published in the last minute; confirm previously-seen headlines remain retrievable after they scroll out of the live panel.

**Acceptance Scenarios**:

1. **Given** the app has just started, **When** the news panel populates from the Press TV (or any other) feed, **Then** each item shows its real publish date/time, not the current fetch time.
2. **Given** an RSS item has no usable publish date in its feed data, **When** it is displayed, **Then** the app clearly marks the timestamp as unknown/approximate rather than silently showing it as brand-new.
3. **Given** the app has been running for a while and older headlines have scrolled out of the visible news panel, **When** the user wants to review them, **Then** the previously fetched headlines are available in a news log.

---

### User Story 2 - Jump straight to the full article (Priority: P2)

As a user scanning headlines, I want to click a "read more" affordance on a news item and be taken straight to the original article, so I don't have to manually search for the story.

**Why this priority**: Small, high-value interaction improvement that builds directly on the feed the user just learned to trust in Story 1.

**Independent Test**: Click "read more" on any news item and confirm the linked article opens.

**Acceptance Scenarios**:

1. **Given** a news item with a valid source link, **When** the user clicks its "read more" affordance, **Then** the article opens in the user's default web browser.
2. **Given** a news item whose source link is missing or malformed, **When** the user looks at that item, **Then** no broken "read more" affordance is offered for it.

---

### User Story 3 - Understand what each signal indicator means and why it matters (Priority: P3)

As a user reading the Slope / Bollinger Bands (BB) / ROC / RSI / MACD / Z-Score indicator badges on the metal panel, I want to click a badge to see a plain-language description of what it measures, and I want the badges ordered by how much weight each signal deserves with a short "why," so I can judge the panel's signals instead of treating them as noise.

**Why this priority**: Valuable and requested, but purely informational — it doesn't fix a bug or unblock a broken workflow, so it follows the data-integrity and read-more fixes.

**Independent Test**: Click each indicator badge in the metal panel and confirm a description appears; confirm the badges are laid out in the documented priority order.

**Acceptance Scenarios**:

1. **Given** the metal panel is showing active indicator badges, **When** the user clicks/presses a badge, **Then** a description of that indicator (what it measures, what a signal from it means) is shown.
2. **Given** multiple indicator badges are visible at once, **When** the user views the panel, **Then** they are ordered from highest to lowest priority, and each description explains why it ranks where it does relative to the others.
3. **Given** the user clicks the same badge again (or clicks elsewhere), **When** the description is already open, **Then** it closes/toggles away without affecting the live indicator values underneath.

---

### User Story 4 - See when the macro calendar is auto-refreshing (Priority: P4)

As a user watching the macro economic calendar, once a scheduled event's time has passed by about a minute, I want the app to automatically fetch the actual released figure and show a visible spinner while it's doing so, so I know the panel is working and I'm not looking at stale data.

**Why this priority**: The underlying auto-fetch-after-the-event mechanism already exists; this story only adds visible feedback, so it's lower risk/value than the fixes above.

**Independent Test**: Wait for a scheduled calendar event's time to pass by roughly a minute and observe a spinner appear on that row while the actual figure is being fetched, then disappear once the figure lands (or the attempt fails).

**Acceptance Scenarios**:

1. **Given** a calendar event's scheduled time passed at least one minute ago and its actual figure hasn't been fetched yet, **When** the app performs the automatic fetch, **Then** a spinner is shown on that event's row for the duration of the fetch.
2. **Given** the fetch completes (success or failure), **When** the result is known, **Then** the spinner is replaced by the actual figure or a clear "unavailable" state.

---

### User Story 5 - Read symbols and report titles as plain names (Priority: P5)

As a user, I want tickers like "Au" and "DXY" shown as readable names, and gold/silver reports labeled "Gold"/"Silver" rather than their short ticker, so I don't have to mentally translate ticker codes while scanning the dashboard.

**Why this priority**: Cosmetic clarity improvement with no functional risk; ordered after the fixes that touch data correctness and interaction.

**Independent Test**: Locate every on-screen spot currently showing "Au" or "DXY" and confirm each now shows a readable name; open the gold and silver report list/screen and confirm entries read "Gold"/"Silver".

**Acceptance Scenarios**:

1. **Given** the gold/silver ratio tile and the dollar index tile are visible, **When** the user views them, **Then** they show readable names instead of "Au"/"DXY" ticker shorthand.
2. **Given** the report screen lists the gold and silver reports, **When** the user views the list, **Then** each entry is labeled "Gold" / "Silver" rather than "XAU" / "XAG".

---

### User Story 6 - Generate reports for copper and oil (Priority: P6)

As a user who already tracks copper and oil tiles, I want to generate the same kind of analysis report for them as I can for gold and silver, so I get the same depth of insight on those commodities.

**Why this priority**: Net-new capability rather than a fix to something broken; it's valuable but the least urgent of the six requests.

**Independent Test**: From the report screen, trigger report generation for copper and for oil and confirm each produces a report in the same style/location as the existing gold/silver reports.

**Acceptance Scenarios**:

1. **Given** the report screen, **When** the user requests report generation, **Then** copper and oil are available alongside gold and silver as generatable report tickers.
2. **Given** a copper or oil report has been generated, **When** the user opens it, **Then** it is labeled "Copper" / "Oil" (not a ticker code) and follows the same report structure/sections as the existing gold/silver reports.

---

### User Story 7 - Track USA and Sweden policy interest rates (Priority: P7)

As a user, I want to see the current USA and Sweden central bank interest rates on the dashboard, so I can factor policy-rate context into gold/silver moves without leaving the app.

**Why this priority**: Net-new data coverage requested alongside the report expansion; useful context but not blocking any existing workflow, so it lands after the other fixes and additions.

**Independent Test**: Open the dashboard and confirm a current USA rate value and a current Sweden rate value are both visible.

**Acceptance Scenarios**:

1. **Given** the dashboard is open, **When** the user looks at the interest-rate tiles, **Then** the current USA policy rate and the current Sweden policy rate are both shown.
2. **Given** a policy rate changes at a central bank meeting, **When** the app next refreshes that tile, **Then** the displayed rate reflects the new value.

---

### User Story 8 - Track German, French, British, and Japanese stock exchanges (Priority: P8)

As a user, I want to see the DAX, CAC 40, FTSE 100, and Nikkei 225 indices alongside the existing Swedish OMX tracking, so I have a fuller picture of global equity markets that can move alongside gold/silver.

**Why this priority**: Net-new market coverage, lowest urgency of the requested items.

**Independent Test**: Open the dashboard and confirm current levels for the German, French, British, and Japanese exchanges are all visible.

**Acceptance Scenarios**:

1. **Given** the dashboard is open, **When** the user looks at the new index tiles, **Then** the current level and session change for DAX, CAC 40, FTSE 100, and Nikkei 225 are each shown.
2. **Given** one of these exchanges is currently closed for the day, **When** the user views its tile, **Then** the tile shows the last available level along with a clear indication that the exchange is closed, rather than presenting stale data as live.

---

### User Story 9 - Open a full detail chart from a tile's mini chart (Priority: P9)

As a user looking at a stock tile's small sparkline, I want to click it and see the same kind of full detail chart the gold/silver panel has, with a 40-day up/down history strip underneath, so I can judge a stock's recent trend without leaving the dashboard.

**Why this priority**: Valuable drill-down interaction, but net-new and the last of the requested additions — it doesn't fix anything broken and the dashboard remains fully usable without it.

**Independent Test**: Click a stock tile's mini chart and confirm a modal opens showing that stock's full detail chart with a 40-day up/down strip beneath it; confirm closing the modal returns to the live dashboard unaffected.

**Acceptance Scenarios**:

1. **Given** a stock tile showing a mini sparkline chart, **When** the user clicks/presses that mini chart, **Then** a modal opens showing a full detail chart for that instrument, in the same style as the existing gold/silver chart.
2. **Given** the full detail chart modal is open, **When** the user looks below the chart, **Then** they see the last 40 trading days for that instrument, each shown as an up or down arrow with that day's percentage change.
3. **Given** the modal is open, **When** the user dismisses it, **Then** it closes and the live dashboard tiles continue updating exactly as before.

---

### User Story 10 - See report status and dividends in the chart detail modal (Priority: P10)

As a user viewing the full detail chart modal for a stock that's on my report watchlist, I want to see when its next scheduled report will run and where to find its most recent report, plus when the company next pays a dividend and how much, so I have the complete picture for that instrument in one place.

**Why this priority**: Builds directly on Story 9's modal and Story 6's report watchlist; still net-new/informational, so it's ordered last.

**Independent Test**: Add a stock to the report watchlist, open its chart detail modal, and confirm it shows the next scheduled report time, a link to the latest generated report, and the stock's next dividend date/amount (or a clear "no dividend" state).

**Acceptance Scenarios**:

1. **Given** a stock on the report watchlist, **When** its chart detail modal is opened, **Then** the modal shows the next scheduled report generation time for that stock.
2. **Given** a stock on the report watchlist that already has at least one generated report, **When** its chart detail modal is opened, **Then** the modal shows or links to its most recently generated report.
3. **Given** a stock is not on the report watchlist, **When** its chart detail modal is opened, **Then** no report scheduling/history section is shown (rather than an error or empty section).
4. **Given** a stock pays dividends, **When** its chart detail modal is opened, **Then** the modal shows the next known dividend payment date and the dividend amount.
5. **Given** a stock does not pay dividends or dividend data is unavailable, **When** its chart detail modal is opened, **Then** the modal clearly states no dividend information is available.

---

### Edge Cases

- What happens when a news source's feed goes down entirely — does the news log still show the last-known-good headlines, or does the panel go blank?
- What happens if the user clicks "read more" on a headline whose article has since been removed/404s from the source site?
- What happens when two indicator badges are tied in priority — is there a defined tie-break, or is a strict total order guaranteed for all six indicators?
- What happens if a macro calendar event's actual-figure source itself hasn't published the number yet when the 1-minute auto-fetch fires — does the spinner keep spinning, retry, or fall back to an "unavailable" state after a timeout?
- What happens to the readable-name change if the user has limited panel width — do the new longer names (e.g. "US Dollar Index") need to truncate/abbreviate in narrow layouts?
- What happens when copper or oil report generation is requested but the underlying market data for that commodity is temporarily unavailable?
- What happens when a central bank has not changed its policy rate in a long time — does the tile just show the flat current value, or also the date it took effect?
- What happens if a foreign interest-rate or index data source is temporarily unavailable — does the tile show a stale value with an age indicator, or go blank?
- What happens when 40 days of daily history for a stock isn't available yet (newly added ticker, thin trading history) — does the modal show fewer days, or a loading state while it fetches?
- What happens when the user clicks a mini chart that currently has fewer than 2 data points (nothing meaningful to draw yet)?
- What happens when a stock is added to (or removed from) the report watchlist while its chart detail modal is already open — does the report section update live, or only on next open?
- What happens when the dividend data source is temporarily unavailable — does the modal show a stale value with an age indicator, or a clear "unavailable" state?

## Requirements *(mandatory)*

### Functional Requirements

**News feed integrity (Story 1)**

- **FR-001**: The system MUST derive each news item's displayed date/time from the item's actual publish-time data rather than defaulting to the current fetch time when no reliable publish time is available.
- **FR-002**: The system MUST visibly distinguish a news item whose true publish time could not be determined (e.g. an "approximate"/"unknown time" indicator) from one with a confirmed publish time.
- **FR-003**: The system MUST NOT display a news item's timestamp as more recent than the time the item was actually fetched.
- **FR-004**: The system MUST retain a rolling in-session log of previously fetched news items (spanning multiple source refreshes, well beyond the live panel's visible window), so the user can review headlines that have scrolled out of view. The log is in-memory and does not need to survive an app restart.
- **FR-005**: The system MUST make the news log viewable by the user through a "show more" / browsable view reachable from the news panel.

**Read more (Story 2)**

- **FR-006**: Each news item with a valid source link MUST offer a "read more" affordance that opens the original article.
- **FR-007**: Activating "read more" MUST open the article in the user's default web browser.
- **FR-008**: A news item without a usable source link MUST NOT present a "read more" affordance.

**Indicator transparency (Story 3)**

- **FR-009**: Each of the six signal indicators (Slope, Bollinger Bands, ROC, RSI, MACD, Z-Score) MUST have a short, plain-language description of what it measures and what a triggered signal from it means.
- **FR-010**: The user MUST be able to reveal an indicator's description by clicking/pressing its badge in the metal panel, without triggering any other action.
- **FR-011**: Revealing a description a second time (or dismissing it) MUST hide it again; it MUST NOT alter the underlying live indicator computation or values.
- **FR-012**: The six indicators MUST be ranked by signal character — confirmed/slower signals outranking fast/noisier ones — in this order, highest priority first: (1) Z-Score, (2) MACD, (3) Bollinger Bands, (4) RSI, (5) ROC, (6) Slope. Each indicator's description MUST state why it ranks above or below its neighbors in terms of lag vs. noise/false-signal trade-offs (e.g. Z-Score and MACD confirm over a longer window and produce fewer false signals; Slope and ROC react fastest but are the noisiest and most prone to whipsaw).
- **FR-013**: The indicator badges MUST be displayed in the defined priority order (highest priority first) wherever they appear together.

**Macro calendar auto-fetch feedback (Story 4)**

- **FR-014**: When a calendar event's scheduled time has passed by at least one minute and its actual figure has not yet been fetched, the system MUST automatically attempt to fetch that figure.
- **FR-015**: While an automatic actual-figure fetch is in progress for an event, the system MUST show a spinner on that event's row.
- **FR-016**: When the fetch completes, the spinner MUST be replaced by the fetched figure, or by a clear "unavailable" indicator if the fetch failed.

**Readable naming (Story 5)**

- **FR-017**: Every user-facing display of the "Au" gold-ratio ticker shorthand MUST be replaced with a readable name.
- **FR-018**: Every user-facing display of the "DXY" ticker shorthand MUST be replaced with a readable name.
- **FR-019**: The gold and silver report list/screen MUST display "Gold" and "Silver" respectively in place of their short ticker codes.

**Copper & oil reports (Story 6)**

- **FR-020**: The system MUST support generating an analysis report for copper, following the same report structure as the existing gold/silver reports.
- **FR-021**: The system MUST support generating an analysis report for oil, following the same report structure as the existing gold/silver reports.
- **FR-022**: Generated copper and oil reports MUST be labeled with their readable commodity name ("Copper", "Oil"), not a ticker code.
- **FR-023**: Copper and oil MUST appear alongside gold and silver as selectable/generatable entries wherever report generation is triggered, using the same full analysis pipeline (same depth, sections, and generation mechanism) as the existing gold/silver reports.

**Interest rates (Story 7)**

- **FR-024**: The system MUST display the current USA central bank policy interest rate.
- **FR-025**: The system MUST display the current Sweden central bank policy interest rate.
- **FR-026**: Interest rate tiles MUST refresh on a cadence appropriate to how infrequently policy rates change, rather than on the app's fast live-price cadence.
- **FR-027**: The USA and Sweden interest rate tiles MUST be individually selectable/toggleable alongside the existing mini-tiles (USD/SEK, commodities, ratio, DXY, real yield).

**International stock exchanges (Story 8)**

- **FR-028**: The system MUST track and display the German stock exchange index (DAX).
- **FR-029**: The system MUST track and display the French stock exchange index (CAC 40).
- **FR-030**: The system MUST track and display the British stock exchange index (FTSE 100).
- **FR-031**: The system MUST track and display the Japanese stock exchange index (Nikkei 225).
- **FR-032**: Each new index tile MUST show the index's current level and its change (value and/or percent) for the current session, consistent with the existing Swedish OMX tile's display format.
- **FR-033**: Each new index tile MUST indicate when its exchange is closed rather than presenting a stale last-close level as if it were live.
- **FR-034**: The new index tiles MUST be individually selectable/toggleable alongside existing mini-tiles.

**Full chart from mini chart (Story 9)**

- **FR-035**: Clicking/pressing a stock tile's mini sparkline chart MUST open a modal showing that instrument's full detail chart, in the same presentation style as the existing gold/silver chart.
- **FR-036**: The chart modal MUST be dismissible without disrupting the live dashboard underneath, following the app's existing modal pattern (e.g. the calendar event detail modal).
- **FR-037**: The chart modal MUST show, below the full detail chart, a chronological strip of the last 40 trading days for that instrument, each represented as an up or down arrow paired with that day's percentage change.
- **FR-038**: When fewer than 40 trading days of history are available for an instrument, the system MUST show as many days as are available rather than blocking or failing to open the modal.
- **FR-039**: Closing the chart modal MUST leave the tile's live price updates running exactly as before it was opened.

**Report status & dividends in the chart modal (Story 10)**

- **FR-040**: When the instrument shown in the chart detail modal is on the user's report watchlist, the modal MUST show the next scheduled report generation time for that instrument.
- **FR-041**: When the instrument shown in the chart detail modal is on the user's report watchlist and has at least one previously generated report, the modal MUST show or link to the most recently generated report.
- **FR-042**: When the instrument shown in the chart detail modal is not on the user's report watchlist, the modal MUST NOT show report scheduling/history information.
- **FR-043**: The chart detail modal MUST show the instrument's next known dividend payment date, when one exists.
- **FR-044**: The chart detail modal MUST show the dividend amount associated with that upcoming or most recent payment.
- **FR-045**: When an instrument pays no dividend or dividend data is unavailable, the modal MUST clearly indicate that rather than leaving a blank or misleading field.

### Key Entities

- **News Item**: A single headline from a source feed — source name, title, link, and publish timestamp (now distinguished as confirmed vs. unknown/approximate).
- **News Log**: The retained history of news items beyond the live panel's visible window, browsable by the user.
- **Indicator Definition**: The static description content for one of the six signal indicators — name, plain-language explanation, and its assigned priority rank with rationale text.
- **Calendar Event Auto-Fetch State**: The in-progress/complete/failed state of a scheduled calendar event's automatic actual-figure fetch, driving the spinner shown on that event's row.
- **Report Ticker**: A commodity eligible for report generation — readable display name, underlying market symbol, and the generated report's location/content. Extended by this feature to include copper and oil alongside the existing gold and silver entries.
- **Policy Interest Rate**: A central bank's current benchmark rate (USA Federal Reserve, Sweden Riksbank) — value and as-of date. Distinct from the app's existing 10-Year TIPS real yield tile, which is unaffected by this feature.
- **Stock Exchange Index**: A national equity index — current level, session change, and trading-session state (open/closed). Extends the existing Swedish OMX tracking to Germany (DAX), France (CAC 40), UK (FTSE 100), and Japan (Nikkei 225).
- **Daily History Strip Entry**: One trading day's summary for an instrument — date, direction (up/down), percentage change — used to render the 40-day strip below the full detail chart.
- **Dividend Payment**: An instrument's dividend data — next or most recent payment date and per-share amount.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a fresh app start, 0% of displayed news timestamps show the current time as the publish time unless the item was genuinely published within the last minute.
- **SC-002**: Users can retrieve any news item published within the retained log window even after it has scrolled out of the live panel, 100% of the time.
- **SC-003**: Clicking "read more" on any news item with a valid link opens the correct source article within 2 seconds, on the first attempt.
- **SC-004**: Users can view a description for any of the six signal indicators within one click/press, with zero impact on live indicator values.
- **SC-005**: 100% of users reviewing the indicator panel can correctly identify which indicator the app considers highest priority, based on the displayed order and description alone.
- **SC-006**: A visible spinner appears within one minute of a calendar event's scheduled time passing (when an actual figure is pending), 100% of the time.
- **SC-007**: Zero instances of "Au" or "DXY" ticker shorthand remain in user-facing text after the change.
- **SC-008**: Users can successfully generate a copper report and an oil report on the first attempt, with the same success rate as existing gold/silver report generation.
- **SC-009**: Users can see the current USA and Sweden policy interest rates on the main dashboard without navigating to another screen.
- **SC-010**: Users can see live levels for DAX, CAC 40, FTSE 100, and Nikkei 225 alongside the existing OMX tile, refreshed on the same cadence as comparable existing index/commodity tiles.
- **SC-011**: Users can open a stock's full detail chart in one click from its mini chart, with the modal appearing as quickly as the app's existing calendar-event detail modal.
- **SC-012**: The 40-day history strip correctly reflects up/down direction and percentage change for the trailing 40 available trading days (or all available days when fewer than 40 exist), verified against the instrument's known price history.
- **SC-013**: Users can see a report-watchlisted stock's next scheduled report time and latest report link within the same modal used to view its chart, without navigating to another screen.
- **SC-014**: Users can see accurate dividend date/amount, or a clear "no dividend" state, for any stock viewed via the chart detail modal.

## Assumptions

- The user's "si" and "mci" refer to the app's existing **RSI** and **MACD** signal indicators (there is no indicator literally named "SI" or "MCI" in the codebase); combined with slope, Bollinger Bands, ROC, and Z-Score, this yields the six indicators covered by this feature.
- "Hidden click" means the description is revealed by clicking/pressing directly on the indicator's existing badge — no new dedicated button or keybinding is introduced.
- "Read more" opens the article in the system's default web browser, since the app is a terminal UI and cannot render web pages itself.
- The macro calendar's existing per-event automatic actual-figure fetch (which already fires shortly after an event's scheduled time, subject to a grace period) is the fetch this feature attaches a spinner to; no new fetch-triggering logic is introduced beyond making the existing fetch visible at the ~1-minute mark.
- "DXY" becomes a readable name such as "US Dollar Index" (or equivalent), and the gold/silver ratio ticker "Au/Ag" becomes a readable label such as "Gold/Silver Ratio"; exact wording is a copy decision made during implementation as long as it is a plain-language name rather than ticker shorthand.
- "Name it gold or silver, not the short name" applies to user-visible labels (report list entries, report titles); internal file-naming/storage may continue to use a filesystem-safe token where needed for uniqueness.
- Copper and oil report generation reuses the existing market data already tracked for those commodities elsewhere in the app (their live tiles) as the basis for the report's reference data.
- "Räntan för USA och Sverige" refers to each country's current central bank policy rate (US Federal Reserve funds rate; Sweden Riksbank rate) — a live/current value, not a historical bond yield — and is additive to, not a replacement for, the app's existing 10-Year TIPS real yield tile.
- The four new exchanges are tracked via their headline index (DAX, CAC 40, FTSE 100, Nikkei 225), mirroring how the existing Swedish market is tracked via the OMX index rather than individual constituent stocks.
- New interest-rate and index tiles are added as additional selectable mini-tiles, consistent with how users already choose which mini-tiles to display, rather than being forced onto the dashboard permanently.
- "The mini chart" refers to the sparkline already rendered on stock tiles (quantum tickers, goldsilver stock tiles). Tiles that show only a numeric value today (commodity, ratio, real-yield, and the new interest-rate/index tiles from Stories 7-8) are out of scope for click-to-open-chart in this feature.
- The full detail chart in the modal mirrors the existing gold/silver chart's presentation, scoped to the clicked instrument's own price history.
- Daily history needed for the 40-day strip is fetched/cached per instrument the same way the app already sources gold/silver's daily history, since stock tiles currently retain only today's intraday closes.
- "My subscribed minicharts" refers to the existing report-watchlist (tickers explicitly added via the report screen's "add ticker" flow), not every stock tile currently displayed on the dashboard — this avoids auto-enrolling every displayed tile into the AI report generation pipeline (which has real per-report latency/cost).
- "Daily reports" refers to the app's existing AI-generated analysis report engine (already run on a recurring schedule), not company-issued quarterly/annual financial reports.
- Dividend data (payment date and amount) is sourced the same way other market data in the app is sourced (via the existing market-data provider integration), since no dividend tracking exists in the app today.
