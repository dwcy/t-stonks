from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx
import yfinance as yf
from pydantic import ValidationError

from goldsilver.data.models_macro import (
    Chamber,
    CongressTrade,
    Party,
    PoliticianStats,
    TradeSide,
)


CongressTradesHandler = Callable[[list[CongressTrade]], Awaitable[None] | None]
CongressTradesStaleHandler = Callable[[datetime], Awaitable[None] | None]

CONGRESS_REFRESH_INTERVAL_S = 900.0
CAPITOLTRADES_BASE = "https://www.capitoltrades.com/trades"
CAPITOLTRADES_PAGES = 4

_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_PARTY_MAP: dict[str, Party] = {
    "republican": "R",
    "democrat": "D",
    "democratic": "D",
    "independent": "I",
    "libertarian": "I",
    "r": "R",
    "d": "D",
    "i": "I",
}

_SIDE_MAP: dict[str, TradeSide] = {
    "buy": "BUY",
    "purchase": "BUY",
    "receive": "BUY",
    "sell": "SELL",
    "sale": "SELL",
    "exchange": "EXCHANGE",
}

_TXID_RE = re.compile(r"_txId")


class CongressTradesService:
    def __init__(
        self,
        handler: CongressTradesHandler | None = None,
        stale_handler: CongressTradesStaleHandler | None = None,
        *,
        refresh_interval_s: float = CONGRESS_REFRESH_INTERVAL_S,
        max_items: int = 80,
        pages: int = CAPITOLTRADES_PAGES,
    ) -> None:
        self._handler = handler
        self._stale_handler = stale_handler
        self._refresh_interval_s = refresh_interval_s
        self._max_items = max_items
        self._pages = pages
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(self._run(), name="congress-loop")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None

    async def refresh_now(self) -> None:
        async with httpx.AsyncClient(
            headers=_HEADERS, timeout=20.0, follow_redirects=True
        ) as client:
            await self._refresh_once(client)

    async def _run(self) -> None:
        async with httpx.AsyncClient(
            headers=_HEADERS, timeout=20.0, follow_redirects=True
        ) as client:
            await self._refresh_once(client)
            while not self._stop.is_set():
                try:
                    await asyncio.wait_for(
                        self._stop.wait(), timeout=self._refresh_interval_s
                    )
                    return
                except asyncio.TimeoutError:
                    pass
                await self._refresh_once(client)

    async def _refresh_once(self, client: httpx.AsyncClient) -> None:
        results = await asyncio.gather(
            *[self._fetch_page(client, p) for p in range(1, self._pages + 1)],
            return_exceptions=True,
        )
        merged: list[CongressTrade] = []
        seen: set[int] = set()
        any_ok = False
        for r in results:
            if isinstance(r, list):
                any_ok = True
                for txid, trade in r:
                    if txid in seen:
                        continue
                    seen.add(txid)
                    merged.append(trade)
        if not any_ok:
            await self._emit_stale()
            return
        merged.sort(key=lambda t: t.traded_at, reverse=True)
        await self._emit(merged[: self._max_items])

    async def _fetch_page(
        self, client: httpx.AsyncClient, page: int
    ) -> list[tuple[int, CongressTrade]]:
        params = {"page": str(page), "pageSize": "24"} if page > 1 else None
        try:
            response = await client.get(CAPITOLTRADES_BASE, params=params)
            response.raise_for_status()
        except httpx.HTTPError:
            return []
        return _parse_page(response.text)

    async def _emit(self, trades: list[CongressTrade]) -> None:
        if self._handler is None:
            return
        result = self._handler(trades)
        if asyncio.iscoroutine(result):
            await result

    async def _emit_stale(self) -> None:
        if self._stale_handler is None:
            return
        result = self._stale_handler(datetime.now(timezone.utc))
        if asyncio.iscoroutine(result):
            await result


def _parse_page(html: str) -> list[tuple[int, CongressTrade]]:
    out: list[tuple[int, CongressTrade]] = []
    seen: set[int] = set()
    for raw in _extract_trade_objects(html):
        trade_obj = _safe_load(raw)
        if trade_obj is None:
            continue
        txid = trade_obj.get("_txId")
        if not isinstance(txid, int) or txid in seen:
            continue
        trade = _obj_to_trade(trade_obj)
        if trade is None:
            continue
        seen.add(txid)
        out.append((txid, trade))
    return out


def _extract_trade_objects(html: str) -> list[str]:
    out: list[str] = []
    length = len(html)
    for m in _TXID_RE.finditer(html):
        i = m.start()
        depth = 0
        start: int | None = None
        for j in range(i, max(0, i - 4000), -1):
            ch = html[j]
            if ch == "}":
                depth += 1
            elif ch == "{":
                if depth == 0:
                    start = j
                    break
                depth -= 1
        if start is None:
            continue
        depth = 0
        end: int | None = None
        in_str = False
        escape = False
        for k in range(start, min(length, start + 6000)):
            ch = html[k]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = k + 1
                    break
        if end is None:
            continue
        out.append(html[start:end])
    return out


def _safe_load(raw: str) -> dict[str, Any] | None:
    try:
        unescaped = raw.encode("utf-8").decode("unicode_escape")
    except UnicodeDecodeError:
        return None
    try:
        obj = json.loads(unescaped)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    return obj


def _obj_to_trade(obj: dict[str, Any]) -> CongressTrade | None:
    pol = obj.get("politician")
    issuer = obj.get("issuer")
    if not isinstance(pol, dict) or not isinstance(issuer, dict):
        return None
    first = str(pol.get("firstName") or "").strip()
    last = str(pol.get("lastName") or "").strip()
    if last and first:
        name = f"{last}, {first[:1]}."
    else:
        name = (last or first or str(pol.get("fullName") or "")).strip()
    if not name:
        return None
    party_raw = str(pol.get("party") or "").strip().lower()
    party = _PARTY_MAP.get(party_raw, "I")
    chamber_raw = str(pol.get("chamber") or obj.get("chamber") or "").strip().lower()
    chamber: Chamber = "SENATE" if chamber_raw.startswith("senate") else "HOUSE"
    ticker_raw = str(issuer.get("issuerTicker") or "").strip().upper()
    if not ticker_raw or ticker_raw in {"N/A", "--", "NONE"}:
        return None
    ticker = ticker_raw.split(":", 1)[0]
    side_raw = str(obj.get("txType") or "").strip().lower()
    side = _SIDE_MAP.get(side_raw)
    if side is None:
        return None
    value = obj.get("value")
    if isinstance(value, (int, float)) and value > 0:
        size_bucket = f"~${_format_dollars(float(value))}"
    else:
        size_bucket = str(obj.get("size") or obj.get("amount") or "n/a")
    traded_at = _parse_date(obj.get("txDate"))
    if traded_at is None:
        return None
    filed_at = _parse_date(obj.get("pubDate"))
    try:
        return CongressTrade(
            politician=name,
            party=party,
            chamber=chamber,
            ticker=ticker,
            asset_name=str(issuer.get("issuerName") or "").strip(),
            side=side,
            size_bucket=size_bucket,
            traded_at=traded_at,
            filed_at=filed_at,
        )
    except ValidationError:
        return None


def _format_dollars(amount: float) -> str:
    if amount >= 1_000_000:
        return f"{amount / 1_000_000:.1f}M"
    if amount >= 1_000:
        return f"{amount / 1_000:.0f}K"
    return f"{amount:.0f}"


def _parse_date(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    for cand in (text, text.replace("Z", "+00:00")):
        try:
            dt = datetime.fromisoformat(cand)
        except ValueError:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            dt = datetime.strptime(text, fmt)
        except ValueError:
            continue
        return dt.replace(tzinfo=timezone.utc)
    return None


_MISSING_RETRY = timedelta(hours=1)
_CACHE_TTL = timedelta(hours=24)


class ReturnsCalculator:
    def __init__(self) -> None:
        self._cache: dict[str, dict[date, float]] = {}
        self._latest: dict[str, float] = {}
        self._missing: dict[str, datetime] = {}
        self._fetched_at: dict[str, datetime] = {}

    def _expire(self, now: datetime) -> None:
        for tk, at in list(self._missing.items()):
            if now - at >= _MISSING_RETRY:
                del self._missing[tk]
        for tk, at in list(self._fetched_at.items()):
            if now - at >= _CACHE_TTL:
                self._cache.pop(tk, None)
                self._latest.pop(tk, None)
                del self._fetched_at[tk]

    async def compute(
        self, trades: list[CongressTrade]
    ) -> dict[tuple[str, str, datetime], float | None]:
        tickers: set[str] = set()
        earliest: dict[str, date] = {}
        for t in trades:
            if t.side != "BUY":
                continue
            tickers.add(t.ticker)
            d = t.traded_at.date()
            cur = earliest.get(t.ticker)
            if cur is None or d < cur:
                earliest[t.ticker] = d
        now = datetime.now(timezone.utc)
        self._expire(now)
        to_fetch = [
            tk for tk in tickers if tk not in self._cache and tk not in self._missing
        ]
        if to_fetch:
            fetched = await asyncio.to_thread(_fetch_history_batch, to_fetch, earliest)
            for tk, closes in fetched.items():
                if not closes:
                    self._missing[tk] = now
                    continue
                self._cache[tk] = closes
                self._fetched_at[tk] = now
                last_date = max(closes.keys())
                self._latest[tk] = closes[last_date]
        out: dict[tuple[str, str, datetime], float | None] = {}
        for t in trades:
            key = (t.politician, t.ticker, t.traded_at)
            if t.side != "BUY":
                out[key] = None
                continue
            closes = self._cache.get(t.ticker)
            if not closes:
                out[key] = None
                continue
            entry = _close_on_or_after(closes, t.traded_at.date())
            current = self._latest.get(t.ticker)
            if entry is None or current is None or entry <= 0:
                out[key] = None
                continue
            out[key] = (current - entry) / entry * 100.0
        return out


def _fetch_history_batch(
    tickers: list[str], earliest: dict[str, date]
) -> dict[str, dict[date, float]]:
    out: dict[str, dict[date, float]] = {}
    today = datetime.now(timezone.utc).date()
    end = today + timedelta(days=1)
    for tk in tickers:
        start = earliest.get(tk, today - timedelta(days=365))
        start = start - timedelta(days=5)
        try:
            df = yf.Ticker(tk).history(
                start=start.isoformat(),
                end=end.isoformat(),
                interval="1d",
                auto_adjust=False,
            )
        except Exception:
            out[tk] = {}
            continue
        if df is None or len(df) == 0:
            out[tk] = {}
            continue
        closes: dict[date, float] = {}
        try:
            for idx, value in df["Close"].items():
                if value != value:
                    continue
                if hasattr(idx, "to_pydatetime"):
                    d = idx.to_pydatetime().date()
                elif hasattr(idx, "date"):
                    d = idx.date()
                else:
                    continue
                closes[d] = float(value)
        except Exception:
            closes = {}
        out[tk] = closes
    return out


def _close_on_or_after(closes: dict[date, float], target: date) -> float | None:
    if not closes:
        return None
    if target in closes:
        return closes[target]
    later = sorted(d for d in closes.keys() if d >= target)
    if later:
        return closes[later[0]]
    # No close on/after the trade date yet: an earlier close would equal
    # "current" and fake a 0% return, so report no data instead.
    return None


def compute_politician_stats(
    trades: list[CongressTrade],
    returns: dict[tuple[str, str, datetime], float | None],
    *,
    window_days: int = 30,
    min_trades: int = 1,
) -> list[PoliticianStats]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    by_pol: dict[str, list[CongressTrade]] = {}
    for t in trades:
        if t.traded_at < cutoff:
            continue
        by_pol.setdefault(t.politician, []).append(t)
    stats: list[PoliticianStats] = []
    for name, group in by_pol.items():
        if len(group) < min_trades:
            continue
        buys = [t for t in group if t.side == "BUY"]
        buy_returns = [
            r
            for t in buys
            if (r := returns.get((t.politician, t.ticker, t.traded_at))) is not None
        ]
        avg_return: float | None
        win_rate: float | None
        if buy_returns:
            avg_return = sum(buy_returns) / len(buy_returns)
            wins = sum(1 for r in buy_returns if r > 0)
            win_rate = wins / len(buy_returns) * 100.0
        else:
            avg_return = None
            win_rate = None
        latest = max(t.traded_at for t in group)
        first = group[0]
        try:
            stats.append(
                PoliticianStats(
                    politician=name,
                    party=first.party,
                    chamber=first.chamber,
                    trade_count=len(group),
                    buy_count=len(buys),
                    avg_return_pct=avg_return,
                    win_rate_pct=win_rate,
                    last_trade_at=latest,
                )
            )
        except ValidationError:
            continue
    stats.sort(
        key=lambda s: (
            s.avg_return_pct if s.avg_return_pct is not None else float("-inf")
        ),
        reverse=True,
    )
    return stats
