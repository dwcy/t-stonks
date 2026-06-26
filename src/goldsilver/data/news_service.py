"""Facade: NewsService relocated to marketcore; defaults to goldsilver's feed set."""

from __future__ import annotations

from marketcore.services.news_service import (
    NEWS_REFRESH_INTERVAL_S,
    TRUMP_REFRESH_INTERVAL_S,
    NewsHandler,
    NewsStaleHandler,
    TrumpService,
    _parse_rss,
)
from marketcore.services.news_service import NewsService as _CoreNewsService

from goldsilver.data.news_feeds import NEWS_FEEDS

__all__ = [
    "NEWS_FEEDS",
    "NEWS_REFRESH_INTERVAL_S",
    "TRUMP_REFRESH_INTERVAL_S",
    "NewsService",
    "TrumpService",
    "_parse_rss",
]


class NewsService(_CoreNewsService):
    def __init__(
        self,
        handler: NewsHandler | None = None,
        stale_handler: NewsStaleHandler | None = None,
        *,
        refresh_interval_s: float = NEWS_REFRESH_INTERVAL_S,
        max_items: int = 200,
        per_source_cap: int = 5,
    ) -> None:
        super().__init__(
            NEWS_FEEDS,
            handler,
            stale_handler,
            refresh_interval_s=refresh_interval_s,
            max_items=max_items,
            per_source_cap=per_source_cap,
        )
