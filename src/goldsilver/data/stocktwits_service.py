from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

import httpx
from pydantic import ValidationError

from goldsilver.data.models_macro import Sentiment, StockTwitMessage


StockTwitsHandler = Callable[[list[StockTwitMessage]], Awaitable[None] | None]
StockTwitsStaleHandler = Callable[[datetime], Awaitable[None] | None]

STOCKTWITS_REFRESH_INTERVAL_S = 180.0
STOCKTWITS_DEFAULT_TICKERS: tuple[str, ...] = ("DJT", "GLD", "SLV")
STOCKTWITS_URL = "https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
_USER_AGENT = "gold-and-silver TUI"
_HEADERS = {"User-Agent": _USER_AGENT, "Accept": "application/json"}

_SENTIMENT_MAP: dict[str, Sentiment] = {
    "bullish": "BULL",
    "bearish": "BEAR",
}


class StockTwitsService:
    def __init__(
        self,
        handler: StockTwitsHandler | None = None,
        stale_handler: StockTwitsStaleHandler | None = None,
        *,
        tickers: tuple[str, ...] = STOCKTWITS_DEFAULT_TICKERS,
        refresh_interval_s: float = STOCKTWITS_REFRESH_INTERVAL_S,
        max_items: int = 50,
        per_ticker_cap: int = 12,
    ) -> None:
        self._handler = handler
        self._stale_handler = stale_handler
        self._tickers = tuple(tickers)
        self._refresh_interval_s = refresh_interval_s
        self._max_items = max_items
        self._per_ticker_cap = per_ticker_cap
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    def start(self) -> None:
        if not self._tickers:
            return
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(self._run(), name="stocktwits-loop")

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
            headers=_HEADERS, timeout=15.0, follow_redirects=True
        ) as client:
            await self._refresh_once(client)

    async def _run(self) -> None:
        async with httpx.AsyncClient(
            headers=_HEADERS, timeout=15.0, follow_redirects=True
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
            *[self._fetch_ticker(client, t) for t in self._tickers],
            return_exceptions=True,
        )
        merged: list[StockTwitMessage] = []
        seen: set[int] = set()
        any_ok = False
        for r in results:
            if isinstance(r, list):
                any_ok = True
                for msg in r:
                    if msg.id in seen:
                        continue
                    seen.add(msg.id)
                    merged.append(msg)
        if not any_ok:
            await self._emit_stale()
            return
        merged.sort(key=lambda m: m.created_at, reverse=True)
        await self._emit(merged[: self._max_items])

    async def _fetch_ticker(
        self, client: httpx.AsyncClient, ticker: str
    ) -> list[StockTwitMessage]:
        try:
            response = await client.get(
                STOCKTWITS_URL.format(ticker=ticker),
                params={"limit": str(self._per_ticker_cap)},
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            return []
        return _parse_stream(payload, ticker)

    async def _emit(self, messages: list[StockTwitMessage]) -> None:
        if self._handler is None:
            return
        result = self._handler(messages)
        if asyncio.iscoroutine(result):
            await result

    async def _emit_stale(self) -> None:
        if self._stale_handler is None:
            return
        result = self._stale_handler(datetime.now(timezone.utc))
        if asyncio.iscoroutine(result):
            await result


def _parse_stream(payload: Any, source_ticker: str) -> list[StockTwitMessage]:
    if not isinstance(payload, dict):
        return []
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return []
    out: list[StockTwitMessage] = []
    for raw in messages:
        msg = _parse_message(raw, source_ticker)
        if msg is not None:
            out.append(msg)
    return out


def _parse_message(raw: Any, source_ticker: str) -> StockTwitMessage | None:
    if not isinstance(raw, dict):
        return None
    msg_id = raw.get("id")
    body = raw.get("body") or ""
    created_text = raw.get("created_at") or ""
    user = raw.get("user") or {}
    if not isinstance(user, dict):
        return None
    username = user.get("username") or ""
    if not isinstance(msg_id, int) or not body.strip() or not username:
        return None
    created = _parse_iso(created_text)
    if created is None:
        return None
    entities = raw.get("entities") or {}
    sentiment_raw = (
        entities.get("sentiment") if isinstance(entities, dict) else None
    )
    sentiment: Sentiment | None = None
    if isinstance(sentiment_raw, dict):
        basic = str(sentiment_raw.get("basic") or "").strip().lower()
        sentiment = _SENTIMENT_MAP.get(basic)
    symbols = raw.get("symbols")
    tickers: list[str] = []
    if isinstance(symbols, list):
        for s in symbols:
            if isinstance(s, dict):
                sym = s.get("symbol")
                if isinstance(sym, str) and sym.strip():
                    tickers.append(sym.strip().upper())
    followers = 0
    raw_followers = user.get("followers")
    if isinstance(raw_followers, int):
        followers = raw_followers
    try:
        return StockTwitMessage(
            id=msg_id,
            user_username=username,
            user_followers=followers,
            body=body.strip(),
            sentiment=sentiment,
            tickers=tuple(tickers),
            created_at=created,
            source_ticker=source_ticker,
        )
    except ValidationError:
        return None


def _parse_iso(text: str) -> datetime | None:
    if not text:
        return None
    cleaned = text.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(cleaned)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
