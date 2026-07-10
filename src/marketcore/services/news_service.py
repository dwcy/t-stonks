# > 200 LoC justified: cohesive RSS feed poller + parser kept in one module
"""News feed services — poll injected RSS feeds, parse to NewsItem, emit batches."""

from __future__ import annotations

import asyncio
import re
from collections import deque
from collections.abc import Awaitable, Callable, Sequence
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

import httpx
from pydantic import ValidationError

from marketcore.http import make_client
from marketcore.models_macro import NewsItem, NewsSource, NewsTimeConfidence
from marketcore.services.base import PollingService

NewsHandler = Callable[[list[NewsItem]], Awaitable[None] | None]
NewsStaleHandler = Callable[[datetime], Awaitable[None] | None]
FeedEntry = tuple[NewsSource, str]

NEWS_REFRESH_INTERVAL_S = 30.0
TRUMP_REFRESH_INTERVAL_S = 120.0
TRUMP_FEED_URL = "https://trumpstruth.org/feed"
NEWS_HISTORY_MAX = 300
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


class _FeedService(PollingService[list[NewsItem]]):
    """Feed poller that holds one httpx client open across the polling loop."""

    def __init__(
        self,
        handler: NewsHandler | None,
        stale_handler: NewsStaleHandler | None,
        refresh_interval_s: float,
        task_name: str,
        *,
        history_max: int = NEWS_HISTORY_MAX,
    ) -> None:
        super().__init__(handler, stale_handler, refresh_interval_s, task_name)
        self._history: deque[NewsItem] = deque(maxlen=history_max)

    def history(self) -> tuple[NewsItem, ...]:
        """Items retained beyond the live panel's max_items/per-source cap."""
        return tuple(self._history)

    def _record_history(self, items: Sequence[NewsItem]) -> None:
        seen_urls = {i.url for i in self._history}
        for item in items:
            if item.url in seen_urls:
                continue
            seen_urls.add(item.url)
            self._history.append(item)

    async def refresh_now(self) -> None:
        async with make_client(
            headers=_HEADERS, timeout=10.0, follow_redirects=True
        ) as client:
            await self._refresh_feed(client)

    async def _run(self) -> None:
        async with make_client(
            headers=_HEADERS, timeout=10.0, follow_redirects=True
        ) as client:
            await self._refresh_feed(client)
            while not self._stop.is_set():
                try:
                    await asyncio.wait_for(
                        self._stop.wait(), timeout=self._refresh_interval_s
                    )
                    return
                except asyncio.TimeoutError:
                    pass
                await self._refresh_feed(client)

    async def _refresh_feed(self, client: httpx.AsyncClient) -> None:
        raise NotImplementedError


class NewsService(_FeedService):
    def __init__(
        self,
        feeds: Sequence[FeedEntry],
        handler: NewsHandler | None = None,
        stale_handler: NewsStaleHandler | None = None,
        *,
        refresh_interval_s: float = NEWS_REFRESH_INTERVAL_S,
        max_items: int = 200,
        per_source_cap: int = 5,
        history_max: int = NEWS_HISTORY_MAX,
    ) -> None:
        super().__init__(
            handler,
            stale_handler,
            refresh_interval_s,
            "news-loop",
            history_max=history_max,
        )
        self._feeds = tuple(feeds)
        self._max_items = max_items
        self._per_source_cap = per_source_cap

    async def _refresh_feed(self, client: httpx.AsyncClient) -> None:
        results = await asyncio.gather(
            *[self._fetch_feed(client, src, url) for src, url in self._feeds],
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
        self._record_history(merged)
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
        history_max: int = NEWS_HISTORY_MAX,
    ) -> None:
        super().__init__(
            handler,
            stale_handler,
            refresh_interval_s,
            "trump-loop",
            history_max=history_max,
        )
        self._max_items = max_items

    async def _refresh_feed(self, client: httpx.AsyncClient) -> None:
        try:
            response = await client.get(TRUMP_FEED_URL)
            response.raise_for_status()
            root = ET.fromstring(response.content)
        except (httpx.HTTPError, ET.ParseError):
            await self._emit_stale()
            return
        items = _parse_rss(root, "TRUMP", title_from_description=True)
        self._record_history(items)
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
        confidence: NewsTimeConfidence = "confirmed"
        if published is None:
            # No real <pubDate> — everything from here on is a guessed timestamp,
            # never as trustworthy as a value the feed actually published.
            confidence = "approximate"
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
                    time_confidence=confidence,
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
