# Upstream API Contracts

What the TUI calls, what shape it expects back, what it considers a contract violation.

---

## 1. FRED `releases/dates` — US economic calendar

**URL**: `https://api.stlouisfed.org/fred/releases/dates`

**Method**: `GET`

**Query parameters used**:

| Param | Value | Notes |
|---|---|---|
| `api_key` | `$GOLDSILVER_FRED_KEY` | Required (env var). |
| `file_type` | `json` | |
| `realtime_start` | `today_utc` | |
| `realtime_end` | `today_utc + 6 days` | |
| `include_release_dates_with_no_data` | `true` | Want forward-looking placeholders. |
| `limit` | `1000` | Headroom; expected ≪ 100 per week. |
| `sort_order` | `asc` | |

**Auth**: Free API key, register at https://fred.stlouisfed.org/.

**Expected response (success)**:

```json
{
  "release_dates": [
    {
      "release_id": 10,
      "release_name": "Consumer Price Index",
      "date": "2026-06-11"
    },
    ...
  ]
}
```

**Pydantic model**:

```text
class FredReleaseDate(BaseModel):
    release_id: int
    release_name: str
    date: date

class FredReleasesDatesResponse(BaseModel):
    release_dates: list[FredReleaseDate]
```

**Time handling**: FRED returns only `date`, not time-of-day. Map to a `CalendarEvent` with
`all_day=True`. (Reality: most US releases publish at 08:30 ET; if we later want exact times
we can hardcode per-release publication times, but that is out of MVP scope.)

**Failure modes**:

- 4xx (bad key, missing key) → service emits status `unavailable` for US-releases subset only;
  static FOMC / ECB / Riksbank still rendered.
- 5xx / network error → backoff (initial 1s, doubling, cap 5 min); retain last snapshot, mark
  `stale`.
- Empty `release_dates` array within a 7-day window → treat as `ok` (uncommon but valid;
  e.g. a US holiday week).

**Rate-limit budget**: ≤ 6 req/h (10 min cadence). FRED published limit is 120 req/min — we
use < 0.1% of it.

---

## 2. Static yearly schedules — FOMC / ECB / Riksbank

**Not network calls.** In-process Pydantic-validated lists of `CalendarEvent` literals.

**Source files** (committed):

```text
src/goldsilver/data/calendar_static.py
  FOMC_2026:      list[CalendarEvent]   # ~8 entries
  ECB_2026:       list[CalendarEvent]   # ~8 entries
  RIKSBANK_2026:  list[CalendarEvent]   # ~5–8 entries
  # add _2027 in late 2026; the loader merges by year
```

**Loader contract**: `load_static_events(window_start: date, window_end: date) -> list[CalendarEvent]`
returns all static events whose `scheduled_time.astimezone(STK).date()` falls in
`[window_start, window_end]`.

**Time handling**: ECB and FOMC press conferences have well-known scheduled times (FOMC
statement 14:00 ET, Powell press 14:30 ET; ECB statement 14:15 CET, Lagarde press 14:45 CET).
These are written into the static data with the correct UTC `scheduled_time`.

---

## 3. Riksbank SWEA — FX rates

**URLs**:

- USD/SEK latest: `https://api.riksbank.se/swea/v1/Observations/Latest/sekusdpmi`
- CAD/SEK latest: `https://api.riksbank.se/swea/v1/Observations/Latest/sekcadpmi`
- Series history (for previous close): `https://api.riksbank.se/swea/v1/Observations/sekusdpmi?from=YYYY-MM-DD&to=YYYY-MM-DD`

**Method**: `GET`

**Auth**: none.

**Expected response (latest)**:

```json
{
  "date": "2026-05-27",
  "value": 10.4321
}
```

(Field names verified from public Riksbank documentation; if upstream differs, adjust the
Pydantic schema, not the rest of the pipeline.)

**Pydantic model**:

```text
class RiksbankObservation(BaseModel):
    date: date
    value: float

    @field_validator("value")
    @classmethod
    def _sanity(cls, v: float) -> float:
        if v < 1.0:
            raise ValueError(f"unexpectedly small FX rate: {v}")
        return v
```

**Time handling**: Riksbank publishes one observation per business day, typically by ~11:30
CET. `time` on the `FxRate` is set to `12:00:00 UTC` on the response's `date` — the actual
publish minute isn't returned and the value won't move intraday anyway.

**Previous-close strategy**: on each refresh, also pull `/Observations/{series}?from=date-7d&to=date`
once per business day, take the value before the latest as `previous_close`. Cache the
previous-close locally so the second-per-day pull is plenty.

**Failure modes**:

- HTTP error → backoff (1s, doubling, cap 5 min); switch fallback to Frankfurter after 2
  consecutive failures.
- Parse error / value-validator failure → mark pair `stale`, do not crash.

**Rate-limit budget**: 6 req/h per pair latest + ≤ 1 req/day per pair history = ≤ 14 req/h.

---

## 4. Frankfurter — FX fallback

**URL**: `https://api.frankfurter.dev/v2/rates?base=USD&quotes=SEK,CAD`

**Method**: `GET`

**Auth**: none.

**Expected response**:

```json
{
  "amount": 1.0,
  "base": "USD",
  "date": "2026-05-27",
  "rates": { "SEK": 10.4321, "CAD": 1.3712 }
}
```

**Derivation**:

- `USDSEK = rates.SEK` (SEK per USD).
- `CADSEK = rates.SEK / rates.CAD` (SEK per USD ÷ CAD per USD = SEK per CAD).

**Failure modes**: same backoff as Riksbank. If both fail, FX tiles display `stale`.

---

## 5. yfinance `BZ=F` — Brent oil

**Library call**: `yfinance.Ticker("BZ=F").history(period="2d", interval="1d")`

**Auth**: none.

**Expected response shape** (pandas DataFrame; index is Timestamp):

```
                              Open    High    Low     Close   Volume
2026-05-26 00:00:00+00:00     ...     ...     ...     69.93   ...
2026-05-27 00:00:00+00:00     ...     ...     ...     68.46   ...
```

**Pydantic model** (we already have `Bar` in `data/models.py`, reuse it):

```text
Bar(symbol="BRENT", time=..., open=..., high=..., low=..., close=..., volume=...)
```

**Derivation**:

- `price = last_bar.close`
- `previous_close = second_last_bar.close`

**Failure modes**: `yfinance` raises on no data / empty DataFrame. Wrap call in
`asyncio.to_thread`; on exception, mark `stale` and retain prior value.

**Rate-limit budget**: 6 req/h. yfinance has no published limit but rate-limits per-IP in
practice; one call per 10 min is well within the safe zone.

---

## 6. Existing live feed (unchanged)

`goldprice.org` + Avanza calls in `src/goldsilver/data/service.py` are **unmodified**. The
calendar/FX/Brent additions must not share `httpx.AsyncClient` instances with them (different
hosts, different headers, different failure isolation).
