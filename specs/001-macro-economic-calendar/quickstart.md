# Quickstart: Macro Calendar + FX + Brent

## Prereqs (one-time)

1. **FRED API key** (optional but recommended — without it the US-releases column degrades to
   FOMC-only):

   - Register a free account at `https://fred.stlouisfed.org/`.
   - Apply for a key under "My Account → API Keys".
   - Copy the 32-char key. Set it in your shell environment (do NOT commit it):

     ```bash
     # bash/zsh
     export GOLDSILVER_FRED_KEY="<your 32-char key>"
     ```

     ```powershell
     # PowerShell
     $env:GOLDSILVER_FRED_KEY = "<your 32-char key>"
     ```

   No `.env` file is used; this project follows the global rule "never write env files".

2. **Network reachability** (the TUI fails open — missing endpoints degrade gracefully but the
   user-experience target needs all four upstreams):

   - `api.stlouisfed.org`
   - `api.riksbank.se`
   - `api.frankfurter.dev` (fallback)
   - Yahoo Finance (for `yfinance` Brent + existing chart history)
   - Existing `data-asg.goldprice.org` and `www.avanza.se`

3. **Python deps** — no new packages required if the project already has `httpx`, `pydantic`,
   `yfinance`, `textual`, `textual-plotext`. Verify with `uv tree`. If any are missing they
   should already be transitive deps of the existing live-quote feed.

## Run

```bash
uv sync
uv run goldsilver
```

## What to expect

1. Within ~2 s the metals panels populate (existing behavior).
2. Within ~5 s the calendar panel populates:
   - `Yesterday` (dim gray) shows yesterday's macro events for FED / ECB / Riksbank.
   - `Today` (bright white) shows today's events, with `passed` events dimmed.
   - `Upcoming` (dim gray) shows the next 5 calendar days with one sub-header per day.
3. Within ~15 s the FX strip populates:
   - `USD/SEK <rate> ▲/▼ <pct>% (<abs>)`
   - `CAD/SEK <rate> ▲/▼ <pct>% (<abs>)`
   - `BRENT <price> ▲/▼ <pct>% (<abs>)`
4. All three new feeds refresh every 10 minutes (default).
5. `c` triggers an out-of-band calendar refresh.
6. `f` triggers an out-of-band FX + Brent refresh.

## Verify each user story

| US | Verification |
|---|---|
| US1 (today panel) | Wait until populated. Today's bucket renders in `#e0e0e8` bright text; yesterday + upcoming in `#7a7a8a` gray. |
| US2 (yesterday) | Wait until populated. `Yesterday` header is present even if it has no events (placeholder line). |
| US3 (upcoming 5d) | Count the day sub-headers under `Upcoming` — must be exactly 5. |
| US4 (FX) | Within 15 s, USD/SEK and CAD/SEK show rates > 1.0 with change/% styled green/red. |
| US5 (Brent) | Within 15 s, Brent tile shows price + arrow + change/%. |

## Failure-mode dry-runs

- **Disconnect network mid-run**: live price tile keeps last value, status bar flips to
  `reconnecting`. Calendar / FX / Brent each show `stale since HH:MM`. No crash.
- **Set `GOLDSILVER_FRED_KEY` to a bad value**: calendar still loads FOMC / ECB / Riksbank
  static events. US releases column shows `unavailable (FRED auth)`. No crash.
- **Set the system clock back a day**: on the next minute-tick, bucket assignment recomputes
  and the calendar re-segments automatically. No restart required.

## Yearly maintenance

Each December, refresh the static calendar lists for the next year:

1. Open the ECB's annual indicative calendar (linked from
   `https://www.ecb.europa.eu/press/calendars/`) and copy the 8 Governing Council meeting
   dates + times into `ECB_<year>` in `src/goldsilver/data/calendar_static.py`.
2. Same for FOMC at `https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm`.
3. Same for Riksbank Executive Board at `https://www.riksbank.se/`.
4. Bump the year in the loader's "active year" list.

## Quit

`q` — same as before.
