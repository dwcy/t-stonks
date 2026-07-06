from __future__ import annotations

from marketcore.services.news_service import NewsService


def test_news_service_uses_injected_feeds() -> None:
    feeds = [("X", "http://example.com/rss"), ("Y", "http://example.org/rss")]
    svc = NewsService(feeds)
    assert svc._feeds == tuple(feeds)


def test_goldsilver_newsservice_defaults_to_its_feeds() -> None:
    from goldsilver.data.news_feeds import NEWS_FEEDS
    from goldsilver.data.news_service import NewsService as GsNewsService

    svc = GsNewsService()
    assert svc._feeds == tuple(NEWS_FEEDS)


def test_quantum_feeds_differ_from_goldsilver() -> None:
    from goldsilver.data.news_feeds import NEWS_FEEDS
    from quantum.data.news_feeds import QUANTUM_NEWS_FEEDS

    assert set(QUANTUM_NEWS_FEEDS).isdisjoint(set(NEWS_FEEDS))
