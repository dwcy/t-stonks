from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

import httpx
from pydantic import ValidationError

from goldsilver.data.http import make_client
from goldsilver.data.models_macro import NewsItem, NewsSource


NewsHandler = Callable[[list[NewsItem]], Awaitable[None] | None]
NewsStaleHandler = Callable[[datetime], Awaitable[None] | None]

NEWS_REFRESH_INTERVAL_S = 30.0
TRUMP_REFRESH_INTERVAL_S = 120.0
NEWS_FEEDS: tuple[tuple[NewsSource, str], ...] = (
    (
        "REUTERS",
        "https://news.google.com/rss/search?q=when:24h+site:reuters.com&hl=en-US&gl=US&ceid=US:en",
    ),
    (
        "BLOOMBERG",
        "https://news.google.com/rss/search?q=when:24h+site:bloomberg.com&hl=en-US&gl=US&ceid=US:en",
    ),
    (
        "POLITICO",
        "https://news.google.com/rss/search?q=when:24h+site:politico.com&hl=en-US&gl=US&ceid=US:en",
    ),
    (
        "CNBC",
        "https://www.cnbc.com/id/10000664/device/rss/rss.html",
    ),
    (
        "WllStrtJrnl",
        "https://feeds.content.dowjones.io/public/rss/RSSMarketsMain",
    ),
    (
        "YAHOO",
        "https://finance.yahoo.com/news/rssindex",
    ),
    (
        "FOX",
        "https://moxie.foxbusiness.com/google-publisher/markets.xml",
    ),
    (
        "DgnsIndstr",
        "https://www.di.se/rss",
    ),
    (
        "SVT",
        "https://www.svt.se/nyheter/ekonomi/rss.xml",
    ),
    (
        "BREAKIT",
        "https://www.breakit.se/feed/artiklar",
    ),
    (
        "Placera",
        "https://news.google.com/rss/search?q=when:24h+site:placera.se&hl=sv-SE&gl=SE&ceid=SE:sv",
    ),
    (
        "AffrsVrldn",
        "https://news.google.com/rss/search?q=when:24h+site:affarsvarlden.se&hl=sv-SE&gl=SE&ceid=SE:sv",
    ),
    (
        "REDEYE",
        "https://news.google.com/rss/search?q=when:7d+site:redeye.se&hl=sv-SE&gl=SE&ceid=SE:sv",
    ),
    (
        "BrsKlln",
        "https://news.google.com/rss/search?q=when:24h+site:borskollen.se&hl=sv-SE&gl=SE&ceid=SE:sv",
    ),
    (
        "EFN",
        "https://www.efn.se/rss",
    ),
    (
        "TT",
        "https://news.google.com/rss/search?q=when:24h+site:tt.se&hl=sv-SE&gl=SE&ceid=SE:sv",
    ),
    (
        "WHITEHOUSE",
        "https://www.whitehouse.gov/news/feed/",
    ),
    (
        "PressTV",
        "https://www.presstv.ir/rss.xml",
    ),
    (
        "IRNA",
        "https://en.irna.ir/rss",
    ),
    (
        "MEHR",
        "https://en.mehrnews.com/rss",
    ),
)
TRUMP_FEED_URL = "https://trumpstruth.org/feed"
_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
_HEADERS = {
    "User-Agent": _USER_AGENT,
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}
_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_PLACEHOLDER_PREFIXES = (
    "Headlines -",
    "Placera Forum -",
    "Watchlist -",
    "Stock Screener -",
    "Most Read -",
)
_PLACEHOLDER_LEAD_PATTERNS = (
    re.compile(r"^latest( news)? on .+", re.IGNORECASE),
    re.compile(r"^breaking( news)? on .+", re.IGNORECASE),
    re.compile(r"^news from .+", re.IGNORECASE),
)
_URL_DATE_RE = re.compile(r"/(\d{4})/(\d{2})/(\d{2})/")


def _is_placeholder(title: str) -> bool:
    if any(title.startswith(p) for p in _PLACEHOLDER_PREFIXES):
        return True
    stripped_lead = title.lstrip("-–—•· \t")
    if not stripped_lead or stripped_lead != title:
        if len(stripped_lead.split()) <= 2:
            return True
    parts = title.rsplit(" - ", 1)
    if len(parts) == 2:
        head, tail = parts[0].strip(), parts[1].strip()
        if not head:
            return True
        if head == tail:
            return True
        if head.endswith(f" - {tail}"):
            return True
        if any(p.match(head) for p in _PLACEHOLDER_LEAD_PATTERNS):
            return True
    return False


class _FeedService:
    def __init__(
        self,
        handler: NewsHandler | None,
        stale_handler: NewsStaleHandler | None,
        refresh_interval_s: float,
        task_name: str,
    ) -> None:
        self._handler = handler
        self._stale_handler = stale_handler
        self._refresh_interval_s = refresh_interval_s
        self._task_name = task_name
        self._task: asyncio.Task[None] | None = None
        self._stop = asyncio.Event()

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(self._run(), name=self._task_name)

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
            headers=_HEADERS, timeout=10.0, follow_redirects=True
        ) as client:
            await self._refresh_once(client)

    async def _run(self) -> None:
        async with make_client(
            headers=_HEADERS, timeout=10.0, follow_redirects=True
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
        raise NotImplementedError

    async def _emit(self, items: list[NewsItem]) -> None:
        if self._handler is None:
            return
        result = self._handler(items)
        if asyncio.iscoroutine(result):
            await result

    async def _emit_stale(self) -> None:
        if self._stale_handler is None:
            return
        result = self._stale_handler(datetime.now(timezone.utc))
        if asyncio.iscoroutine(result):
            await result


class NewsService(_FeedService):
    def __init__(
        self,
        handler: NewsHandler | None = None,
        stale_handler: NewsStaleHandler | None = None,
        *,
        refresh_interval_s: float = NEWS_REFRESH_INTERVAL_S,
        max_items: int = 200,
        per_source_cap: int = 5,
    ) -> None:
        super().__init__(handler, stale_handler, refresh_interval_s, "news-loop")
        self._max_items = max_items
        self._per_source_cap = per_source_cap

    async def _refresh_once(self, client: httpx.AsyncClient) -> None:
        results = await asyncio.gather(
            *[self._fetch_feed(client, src, url) for src, url in NEWS_FEEDS],
            return_exceptions=True,
        )
        merged: list[NewsItem] = []
        any_ok = False
        for r in results:
            if isinstance(r, list):
                r.sort(key=lambda i: i.published, reverse=True)
                merged.extend(r[: self._per_source_cap])
                any_ok = True
        if not any_ok:
            await self._emit_stale()
            return
        merged.sort(key=lambda i: i.published, reverse=True)
        await self._emit(merged[: self._max_items])

    async def _fetch_feed(
        self, client: httpx.AsyncClient, source: NewsSource, url: str
    ) -> list[NewsItem]:
        try:
            response = await client.get(url)
            response.raise_for_status()
            root = ET.fromstring(response.content)
        except (httpx.HTTPError, ET.ParseError):
            return []
        return _parse_rss(root, source)


class TrumpService(_FeedService):
    def __init__(
        self,
        handler: NewsHandler | None = None,
        stale_handler: NewsStaleHandler | None = None,
        *,
        refresh_interval_s: float = TRUMP_REFRESH_INTERVAL_S,
        max_items: int = 20,
    ) -> None:
        super().__init__(handler, stale_handler, refresh_interval_s, "trump-loop")
        self._max_items = max_items

    async def _refresh_once(self, client: httpx.AsyncClient) -> None:
        try:
            response = await client.get(TRUMP_FEED_URL)
            response.raise_for_status()
            root = ET.fromstring(response.content)
        except (httpx.HTTPError, ET.ParseError):
            await self._emit_stale()
            return
        items = _parse_rss(root, "TRUMP", title_from_description=True)
        await self._emit(items[: self._max_items])


def _parse_pub_date(value: str) -> datetime | None:
    try:
        dt = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        dt = None
    if dt is None:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _feed_time(root: ET.Element, now: datetime) -> datetime:
    channel = root.find("channel")
    if channel is not None:
        raw = (
            channel.findtext("lastBuildDate") or channel.findtext("pubDate") or ""
        ).strip()
        if raw:
            dt = _parse_pub_date(raw)
            if dt is not None:
                return min(dt, now)
    return now


def _parse_rss(
    root: ET.Element,
    source: NewsSource,
    *,
    title_from_description: bool = False,
) -> list[NewsItem]:
    items: list[NewsItem] = []
    now = datetime.now(timezone.utc)
    feed_time = _feed_time(root, now)
    stagger = 0
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub_text = (item.findtext("pubDate") or "").strip()
        description = (item.findtext("description") or "").strip()
        if title_from_description and (not title or title.startswith("[No Title]")):
            stripped = _TAG_RE.sub(" ", description)
            stripped = _WHITESPACE_RE.sub(" ", stripped).strip()
            if not stripped:
                continue
            title = stripped
        if not title or not link:
            continue
        if _is_placeholder(title):
            continue
        published = _parse_pub_date(pub_text) if pub_text else None
        if published is None:
            published = _date_from_url(link)
            if published is not None and published.date() == feed_time.date():
                published = feed_time - timedelta(minutes=stagger)
                stagger += 1
        if published is None:
            published = now
        if published > now:
            published = now
        try:
            items.append(
                NewsItem(
                    source=source,
                    title=title[:200],
                    url=link,
                    published=published,
                )
            )
        except ValidationError:
            continue
    return items


def _date_from_url(url: str) -> datetime | None:
    m = _URL_DATE_RE.search(url)
    if not m:
        return None
    try:
        return datetime(
            int(m.group(1)),
            int(m.group(2)),
            int(m.group(3)),
            12,
            0,
            tzinfo=timezone.utc,
        )
    except ValueError:
        return None
