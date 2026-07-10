"""News timestamps must never be in the future (wrong-tz / date-only feeds like PressTV)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET

from goldsilver.data.news_service import _parse_rss
from marketcore.models_macro import NewsItem
from marketcore.services.news_service import NewsService


def _now() -> datetime:
    return datetime.now(timezone.utc)


def test_future_pubdate_is_clamped_to_now() -> None:
    future = (_now() + timedelta(days=2)).strftime("%a, %d %b %Y %H:%M:%S GMT")
    xml = (
        "<rss><channel><item>"
        "<title>Headline</title><link>https://e/x</link>"
        f"<pubDate>{future}</pubDate>"
        "</item></channel></rss>"
    )
    items = _parse_rss(ET.fromstring(xml), "MEHR")

    assert items[0].published <= _now()


def test_presstv_url_date_fallback_not_future() -> None:
    today = _now()
    link = (
        f"https://presstv.ir/Detail/{today.year}/{today.month:02d}/{today.day:02d}/1/x"
    )
    xml = (
        "<rss><channel><item>"
        f"<title>Iran news</title><link>{link}</link>"
        "</item></channel></rss>"
    )
    items = _parse_rss(ET.fromstring(xml), "PressTV")

    assert items[0].published <= _now()


def test_presstv_date_only_items_descend_from_build_time() -> None:
    today = _now()
    build = today - timedelta(minutes=30)
    build_str = build.strftime("%a, %d %b %Y %H:%M:%S %z")
    date_path = f"{today.year}/{today.month:02d}/{today.day:02d}"
    xml = (
        "<rss><channel>"
        f"<lastBuildDate>{build_str}</lastBuildDate>"
        f"<item><title>First</title><link>https://presstv.ir/Detail/{date_path}/2/a</link></item>"
        f"<item><title>Second</title><link>https://presstv.ir/Detail/{date_path}/1/b</link></item>"
        "</channel></rss>"
    )
    items = _parse_rss(ET.fromstring(xml), "PressTV")

    assert items[0].published > items[1].published
    assert abs((items[0].published - build).total_seconds()) < 1
    assert all(i.published <= _now() for i in items)


def test_real_pubdate_is_confirmed() -> None:
    pub = _now().strftime("%a, %d %b %Y %H:%M:%S GMT")
    xml = (
        "<rss><channel><item>"
        "<title>Headline</title><link>https://e/x</link>"
        f"<pubDate>{pub}</pubDate>"
        "</item></channel></rss>"
    )
    items = _parse_rss(ET.fromstring(xml), "REUTERS")

    assert items[0].time_confidence == "confirmed"


def test_missing_pubdate_is_approximate() -> None:
    xml = (
        "<rss><channel><item>"
        "<title>Headline</title><link>https://e/x</link>"
        "</item></channel></rss>"
    )
    items = _parse_rss(ET.fromstring(xml), "REUTERS")

    assert items[0].time_confidence == "approximate"


def test_presstv_url_date_fallback_is_approximate() -> None:
    today = _now()
    link = (
        f"https://presstv.ir/Detail/{today.year}/{today.month:02d}/{today.day:02d}/1/x"
    )
    xml = (
        "<rss><channel><item>"
        f"<title>Iran news</title><link>{link}</link>"
        "</item></channel></rss>"
    )
    items = _parse_rss(ET.fromstring(xml), "PressTV")

    assert items[0].time_confidence == "approximate"


def _news_item(url: str, minutes_ago: int) -> NewsItem:
    return NewsItem(
        source="REUTERS",
        title=f"Headline {url}",
        url=url,
        published=_now() - timedelta(minutes=minutes_ago),
    )


def test_history_deque_caps_and_dedupes() -> None:
    service = NewsService(feeds=(), history_max=3)

    service._record_history(
        [_news_item("https://e/1", 3), _news_item("https://e/2", 2)]
    )
    service._record_history(
        [_news_item("https://e/2", 2), _news_item("https://e/3", 1)]
    )
    service._record_history([_news_item("https://e/4", 0)])

    history = service.history()
    assert len(history) == 3
    assert [i.url for i in history] == ["https://e/2", "https://e/3", "https://e/4"]
