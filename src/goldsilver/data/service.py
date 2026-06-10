from __future__ import annotations

import asyncio
import logging
import time as time_mod
from collections.abc import Awaitable, Callable
from datetime import date, datetime, timezone

import httpx
import yfinance as yf

from goldsilver.data.http import make_client
from goldsilver.data.models import Bar, GOLD, SILVER, Tick
from goldsilver.data.session import stockholm_date_of

_log = logging.getLogger(__name__)


TickHandler = Callable[[Tick], Awaitable[None] | None]
StatusHandler = Callable[[str], Awaitable[None] | None]


GOLDPRICE_URL = "https://data-asg.goldprice.org/dbXRates/USD"
GOLDPRICE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://goldprice.org/",
}

AVANZA_INSTRUMENT_URL = "https://www.avanza.se/_api/market-guide/stock/{orderbook_id}"
AVANZA_ORDERBOOK = {GOLD: "18986", SILVER: "18991"}

HISTORICAL_SYMBOL = {GOLD: "GC=F", SILVER: "SI=F"}
POLL_INTERVAL_S = 5.0
AVANZA_REFRESH_INTERVAL_S = 30.0
# Polls can keep succeeding while upstream serves a frozen timestamp; flag it.
STALE_AFTER_FACTOR = 4.0


class _AvanzaSession:
    __slots__ = ("prev_close", "high", "low")

    def __init__(self, prev_close: float, high: float, low: float) -> None:
        self.prev_close = prev_close
        self.high = high
        self.low = low


class MetalsService:
    """Hybrid feed: live spot from goldprice.org, baseline + H/L from Avanza."""

    def __init__(
        self,
        tick_handler: TickHandler | None = None,
        status_handler: StatusHandler | None = None,
        poll_interval_s: float = POLL_INTERVAL_S,
    ) -> None:
        self._tick_handler = tick_handler
        self._status_handler = status_handler
        self._poll_interval_s = poll_interval_s
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._last_ts: int | None = None
        self._avanza: dict[str, _AvanzaSession] = {}
        self._live_high: dict[str, float] = {}
        self._live_low: dict[str, float] = {}
        self._live_session_date: date | None = None
        self._avanza_refresh_task: asyncio.Task[None] | None = None
        self._last_payload_mono: float | None = None
        self._stale_notified = False

    async def fetch_history(
        self, symbol: str, period: str = "1d", interval: str = "1m"
    ) -> list[Bar]:
        yf_symbol = HISTORICAL_SYMBOL.get(symbol, symbol)

        def _sync() -> list[Bar]:
            df = yf.Ticker(yf_symbol).history(period=period, interval=interval)
            bars: list[Bar] = []
            for ts, row in df.iterrows():
                bars.append(
                    Bar(
                        symbol=symbol,
                        time=ts.to_pydatetime(),
                        open=float(row["Open"]),
                        high=float(row["High"]),
                        low=float(row["Low"]),
                        close=float(row["Close"]),
                        volume=float(row["Volume"]),
                    )
                )
            return bars

        return await asyncio.to_thread(_sync)

    async def _fetch_avanza(
        self, client: httpx.AsyncClient, symbol: str
    ) -> _AvanzaSession | None:
        url = AVANZA_INSTRUMENT_URL.format(orderbook_id=AVANZA_ORDERBOOK[symbol])
        try:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()
            prev_close = float(payload["historicalClosingPrices"]["oneDay"])
            q = payload["quote"]
            high = float(q["highest"])
            low = float(q["lowest"])
        except (httpx.HTTPError, KeyError, ValueError, TypeError):
            return None
        return _AvanzaSession(prev_close=prev_close, high=high, low=low)

    async def _refresh_avanza_once(self, client: httpx.AsyncClient) -> None:
        gold, silver = await asyncio.gather(
            self._fetch_avanza(client, GOLD),
            self._fetch_avanza(client, SILVER),
            return_exceptions=True,
        )
        if isinstance(gold, _AvanzaSession):
            self._avanza[GOLD] = gold
        if isinstance(silver, _AvanzaSession):
            self._avanza[SILVER] = silver

    async def _avanza_refresh_loop(self, client: httpx.AsyncClient) -> None:
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(
                    self._stop.wait(), timeout=AVANZA_REFRESH_INTERVAL_S
                )
                return
            except asyncio.TimeoutError:
                pass
            await self._refresh_avanza_once(client)

    def _make_tick(self, symbol: str, price: float, time: datetime) -> Tick:
        tick_date = stockholm_date_of(time)
        if tick_date != self._live_session_date:
            self._live_session_date = tick_date
            self._live_high.clear()
            self._live_low.clear()
        session = self._avanza.get(symbol)
        if session is None:
            baseline = price
            high = max(self._live_high.get(symbol, price), price)
            low = min(self._live_low.get(symbol, price), price)
        else:
            baseline = session.prev_close
            high = max(self._live_high.get(symbol, session.high), session.high, price)
            low = min(self._live_low.get(symbol, session.low), session.low, price)
        self._live_high[symbol] = high
        self._live_low[symbol] = low
        change = price - baseline
        pct = (change / baseline * 100.0) if baseline else 0.0
        return Tick(
            symbol=symbol,
            price=price,
            time=time,
            change=change,
            change_percent=pct,
            day_high=high,
            day_low=low,
            prev_close=baseline,
        )

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop.clear()
            self._last_ts = None
            self._live_high.clear()
            self._live_low.clear()
            self._live_session_date = None
            self._last_payload_mono = None
            self._stale_notified = False
            self._task = asyncio.create_task(self._run(), name="metals-poll")

    async def stop(self) -> None:
        self._stop.set()
        if self._avanza_refresh_task is not None:
            self._avanza_refresh_task.cancel()
            try:
                await self._avanza_refresh_task
            except (asyncio.CancelledError, Exception):
                pass
            self._avanza_refresh_task = None
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None

    def _stale_due(self, now_mono: float) -> bool:
        if self._last_payload_mono is None or self._stale_notified:
            return False
        return (
            now_mono - self._last_payload_mono
            >= self._poll_interval_s * STALE_AFTER_FACTOR
        )

    async def _emit_status(self, status: str) -> None:
        if self._status_handler is None:
            return
        result = self._status_handler(status)
        if asyncio.iscoroutine(result):
            await result

    async def _emit_tick(self, tick: Tick) -> None:
        if self._tick_handler is None:
            return
        result = self._tick_handler(tick)
        if asyncio.iscoroutine(result):
            await result

    async def _handle_payload(self, payload: dict) -> None:
        ts = payload.get("ts")
        if not isinstance(ts, int):
            return
        if self._last_ts is not None and ts <= self._last_ts:
            return
        try:
            item = payload["items"][0]
            gold_price = float(item["xauPrice"])
            silver_price = float(item["xagPrice"])
        except (KeyError, IndexError, ValueError, TypeError):
            return

        self._last_ts = ts
        time = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)

        self._last_payload_mono = time_mod.monotonic()
        self._stale_notified = False
        await self._emit_status("connected")
        await self._emit_tick(self._make_tick(GOLD, gold_price, time))
        await self._emit_tick(self._make_tick(SILVER, silver_price, time))

    async def _run(self) -> None:
        await self._emit_status("connecting")

        async with make_client(timeout=5.0) as avanza_client:
            await self._refresh_avanza_once(avanza_client)
            self._avanza_refresh_task = asyncio.create_task(
                self._avanza_refresh_loop(avanza_client),
                name="avanza-refresh",
            )
            try:
                async with make_client(
                    headers=GOLDPRICE_HEADERS, timeout=5.0
                ) as client:
                    while not self._stop.is_set():
                        try:
                            response = await client.get(GOLDPRICE_URL)
                            response.raise_for_status()
                            await self._handle_payload(response.json())
                        except (httpx.HTTPError, ValueError):
                            await self._emit_status("reconnecting")
                        except asyncio.CancelledError:
                            raise
                        # A handler bug must not silently kill the feed:
                        # surface it as a reconnect and keep polling.
                        except Exception:
                            _log.exception("tick pipeline failed")
                            await self._emit_status("reconnecting")

                        if self._stale_due(time_mod.monotonic()):
                            self._stale_notified = True
                            await self._emit_status("stale")

                        try:
                            await asyncio.wait_for(
                                self._stop.wait(), timeout=self._poll_interval_s
                            )
                            return
                        except asyncio.TimeoutError:
                            continue
            finally:
                refresh_task = self._avanza_refresh_task
                self._avanza_refresh_task = None
                if refresh_task is not None:
                    refresh_task.cancel()
                    try:
                        await refresh_task
                    except (asyncio.CancelledError, Exception):
                        pass
