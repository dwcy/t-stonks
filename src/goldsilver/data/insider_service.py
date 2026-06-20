from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any
from xml.etree import ElementTree as ET

import httpx
from pydantic import ValidationError

from goldsilver.data.http import make_client
from goldsilver.data.models_macro import InsiderSide, InsiderTrade


InsiderTradesHandler = Callable[[list[InsiderTrade]], Awaitable[None] | None]
InsiderTradesStaleHandler = Callable[[datetime], Awaitable[None] | None]

INSIDER_REFRESH_INTERVAL_S = 1800.0
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"

# SEC's fair-access policy asks for a contact in the User-Agent. Read it from
# the environment so no personal address is baked into the source.
SEC_CONTACT_ENV = "GOLDSILVER_SEC_CONTACT"
_DEFAULT_USER_AGENT = "gold-and-silver-tui"
_ACCEPT = "application/json, application/xml, text/xml, */*"


def _headers() -> dict[str, str]:
    contact = os.environ.get(SEC_CONTACT_ENV, "").strip()
    agent = f"{_DEFAULT_USER_AGENT} ({contact})" if contact else _DEFAULT_USER_AGENT
    return {"User-Agent": agent, "Accept": _ACCEPT}


_BUY_CODES = {"P"}
_SELL_CODES = {"S"}


class InsiderTradesService:
    def __init__(
        self,
        handler: InsiderTradesHandler | None = None,
        stale_handler: InsiderTradesStaleHandler | None = None,
        *,
        tickers: tuple[tuple[str, str], ...] = (),
        refresh_interval_s: float = INSIDER_REFRESH_INTERVAL_S,
        max_items: int = 40,
        max_filings_per_ticker: int = 25,
    ) -> None:
        self._handler = handler
        self._stale_handler = stale_handler
        self._tickers = tickers
        self._refresh_interval_s = refresh_interval_s
        self._max_items = max_items
        self._max_filings_per_ticker = max_filings_per_ticker
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()
        self._trade_cache: dict[str, list[InsiderTrade]] = {}

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(self._run(), name="insider-loop")

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
        async with make_client(
            headers=_headers(), timeout=20.0, follow_redirects=True
        ) as client:
            await self._refresh_once(client)

    async def _run(self) -> None:
        async with make_client(
            headers=_headers(), timeout=20.0, follow_redirects=True
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
        any_ok = False
        all_trades: list[InsiderTrade] = []
        for ticker, cik in self._tickers:
            try:
                trades = await self._refresh_one(client, ticker, cik)
            except httpx.HTTPError:
                trades = self._trade_cache.get(cik, [])
            else:
                if trades:
                    any_ok = True
                self._trade_cache[cik] = trades
            all_trades.extend(trades)
        if not any_ok and not all_trades:
            await self._emit_stale()
            return
        all_trades.sort(key=lambda t: t.transaction_date, reverse=True)
        await self._emit(all_trades[: self._max_items])

    async def _refresh_one(
        self, client: httpx.AsyncClient, ticker: str, cik: str
    ) -> list[InsiderTrade]:
        cik = cik.zfill(10)
        response = await client.get(SUBMISSIONS_URL.format(cik=cik))
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            return []
        recent = payload.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        accs = recent.get("accessionNumber", [])
        prims = recent.get("primaryDocument", [])
        filed_dates = recent.get("filingDate", [])
        candidates: list[tuple[str, str, str]] = []
        for form, acc, prim, filed in zip(forms, accs, prims, filed_dates):
            if form != "4" or not acc or not prim:
                continue
            candidates.append((acc, prim, filed))
            if len(candidates) >= self._max_filings_per_ticker:
                break
        if not candidates:
            return []
        cik_int = str(int(cik))
        results = await asyncio.gather(
            *[
                self._fetch_form4(client, cik_int, acc, prim, ticker)
                for acc, prim, _filed in candidates
            ],
            return_exceptions=True,
        )
        out: list[InsiderTrade] = []
        for r in results:
            if isinstance(r, list):
                out.extend(r)
        return out

    async def _fetch_form4(
        self,
        client: httpx.AsyncClient,
        cik_int: str,
        accession: str,
        primary_doc: str,
        fallback_ticker: str,
    ) -> list[InsiderTrade]:
        acc_nodash = accession.replace("-", "")
        filename = primary_doc.split("/")[-1]
        url = f"{ARCHIVES_BASE}/{cik_int}/{acc_nodash}/{filename}"
        try:
            response = await client.get(url)
            response.raise_for_status()
        except httpx.HTTPError:
            return []
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError:
            return []
        return _parse_form4(root, accession, fallback_ticker)

    async def _emit(self, trades: list[InsiderTrade]) -> None:
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


def _parse_form4(
    root: ET.Element, accession: str, fallback_ticker: str
) -> list[InsiderTrade]:
    issuer_ticker = (
        (_text(root, "./issuer/issuerTradingSymbol") or fallback_ticker).strip().upper()
    )
    issuer_name = (_text(root, "./issuer/issuerName") or "").strip()
    insider_name = _text(root, "./reportingOwner/reportingOwnerId/rptOwnerName") or ""
    insider_name = insider_name.strip()
    role = _derive_role(root)

    out: list[InsiderTrade] = []
    for tx in root.findall("./nonDerivativeTable/nonDerivativeTransaction"):
        trade = _parse_transaction(
            tx,
            issuer_ticker=issuer_ticker,
            issuer_name=issuer_name,
            insider_name=insider_name,
            role=role,
            accession=accession,
        )
        if trade is not None:
            out.append(trade)
    for tx in root.findall("./derivativeTable/derivativeTransaction"):
        trade = _parse_transaction(
            tx,
            issuer_ticker=issuer_ticker,
            issuer_name=issuer_name,
            insider_name=insider_name,
            role=role,
            accession=accession,
            derivative=True,
        )
        if trade is not None:
            out.append(trade)
    return out


def _parse_transaction(
    tx: ET.Element,
    *,
    issuer_ticker: str,
    issuer_name: str,
    insider_name: str,
    role: str,
    accession: str,
    derivative: bool = False,
) -> InsiderTrade | None:
    if not insider_name:
        return None
    date_text = _text(tx, "./transactionDate/value")
    if not date_text:
        return None
    try:
        tx_date = datetime.fromisoformat(date_text).replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    code = (_text(tx, "./transactionCoding/transactionCode") or "").strip().upper()
    if not code:
        code = "?"
    acquired_disposed = (
        (_text(tx, "./transactionAmounts/transactionAcquiredDisposedCode/value") or "")
        .strip()
        .upper()
    )
    side = _derive_side(code, acquired_disposed)
    shares = _float(_text(tx, "./transactionAmounts/transactionShares/value"))
    price = _float(_text(tx, "./transactionAmounts/transactionPricePerShare/value"))
    value_usd: float | None = None
    if shares is not None and price is not None:
        value_usd = shares * price
    if derivative:
        role_with = f"{role} (deriv)" if role else "deriv"
    else:
        role_with = role
    try:
        return InsiderTrade(
            issuer_ticker=issuer_ticker,
            issuer_name=issuer_name,
            insider_name=insider_name,
            insider_role=role_with,
            transaction_date=tx_date,
            code=code,
            side=side,
            shares=shares,
            price_per_share=price,
            value_usd=value_usd,
            accession=accession,
        )
    except ValidationError:
        return None


def _derive_side(code: str, acquired_disposed: str) -> InsiderSide:
    if code in _BUY_CODES:
        return "BUY"
    if code in _SELL_CODES:
        return "SELL"
    if acquired_disposed == "A":
        return "BUY"
    if acquired_disposed == "D":
        return "SELL"
    return "OTHER"


def _derive_role(root: ET.Element) -> str:
    rel = root.find("./reportingOwner/reportingOwnerRelationship")
    if rel is None:
        return ""
    flags = []
    if _text(rel, "./isDirector") == "true" or _text(rel, "./isDirector") == "1":
        flags.append("Director")
    if _text(rel, "./isOfficer") == "true" or _text(rel, "./isOfficer") == "1":
        title = (_text(rel, "./officerTitle") or "Officer").strip()
        flags.append(title)
    if (
        _text(rel, "./isTenPercentOwner") == "true"
        or _text(rel, "./isTenPercentOwner") == "1"
    ):
        flags.append("10%+ Owner")
    if _text(rel, "./isOther") == "true" or _text(rel, "./isOther") == "1":
        flags.append("Other")
    return ", ".join(flags)


def _text(element: ET.Element, path: str) -> str | None:
    found = element.find(path)
    if found is None or found.text is None:
        return None
    return found.text


def _float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None
