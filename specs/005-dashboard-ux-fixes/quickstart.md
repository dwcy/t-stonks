# Quickstart: Dashboard UX & Data-Quality Fixes

## Prerequisites

```bash
uv sync
```

A FRED API key is required for the new USA interest-rate tile (reuses the existing
`GOLDSILVER_FRED_KEY` env var already needed for the real-yield tile and macro
calendar). No key is required for the new Sweden interest-rate tile (Riksbank's public
API) or the new index tiles (yfinance).

```bash
# Windows (persist across sessions):
setx GOLDSILVER_FRED_KEY "your-fred-key"
```

## Run

```bash
uv run goldsilver
```

## Manually verifying each story

1. **News timestamps (Story 1)** — start the app fresh; open the news panel and
   confirm no headline shows the current minute as its publish time unless it's
   genuinely brand new. Items the app couldn't confirm a real time for show a `~`
   marker. Leave the app running through a few refresh cycles, then open the news log
   (new binding/button on the panel) and confirm older headlines that scrolled off are
   still listed.
2. **Read more (Story 2)** — click a news item's "read more" affordance; confirm your
   default browser opens the source article.
3. **Indicator descriptions (Story 3)** — in the metal panel, click any of the
   Slope/BB/ROC/RSI/MACD/Z-Score badges; confirm a description + priority rationale
   appears, and the badges are laid out Z-Score → MACD → BB → RSI → ROC → Slope.
4. **Calendar spinner (Story 4)** — watch the macro calendar around a scheduled
   event's time; ~1 minute after it passes, confirm a spinner appears on that row
   until the actual figure resolves (or shows "unavailable").
5. **Readable names (Story 5)** — confirm the ratio tile reads "Gold/Silver Ratio"
   (not "Au/Ag") and the dollar-index tile reads "US Dollar Index" (not "DXY"); open
   the report screen and confirm both the ticker rows and the "recent reports" list
   read "Gold"/"Silver".
6. **Copper & oil reports (Story 6)** — from the report screen, generate a Copper
   report and an Oil report; confirm both appear as pinned entries alongside Gold and
   Silver and produce reports in the same style/location.
7. **Interest rates (Story 7)** — add `FEDRATE` and `RIKSRATE` to your mini-tiles
   (settings screen); confirm both show a current rate value.
8. **International exchanges (Story 8)** — add `DAX`, `CAC40`, `FTSE100`, `NIKKEI225`
   to your mini-tiles; confirm each shows a level + session change, and shows a
   "closed" indicator outside that exchange's trading hours.
9. **Chart detail modal (Story 9)** — click any stock tile's mini sparkline; confirm a
   modal opens with a full chart (same style as the gold/silver chart) and a 40-day
   up/down strip beneath it. Press `escape` to close; confirm the dashboard is
   unaffected.
10. **Report status & dividends (Story 10)** — add a stock ticker to the report
    watchlist (report screen "add ticker"), then open that stock's chart detail modal;
    confirm it shows the next scheduled report time, a link to the latest report (once
    one has run), and the stock's dividend info (or a clear "no dividend
    information" state). Open the modal for a stock **not** on the watchlist and
    confirm the report section is simply absent.

## Config additions

New `AppSettings` fields (goldsilver `settings.json`):

```jsonc
{
  "mini_tiles": ["USDSEK", "RATIO", "DXY", "REALYIELD", "FEDRATE", "RIKSRATE", "DAX", "CAC40", "FTSE100", "NIKKEI225"],
  "report_tickers": ["AAPL"]   // unchanged shape — copper/oil are pinned, not user-added
}
```

No new env vars beyond the already-existing `GOLDSILVER_FRED_KEY`.
