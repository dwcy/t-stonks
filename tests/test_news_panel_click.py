"""Clicking a news item's title opens its article link; malformed links get no affordance."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from textual.app import App, ComposeResult

from goldsilver.data.models_macro import NewsItem
from goldsilver.widgets.news_panel import NewsBody, render_news_row


def _item(url: str) -> NewsItem:
    return NewsItem(
        source="REUTERS",
        title="Headline",
        url=url,
        published=datetime.now(timezone.utc),
    )


class _Harness(App[None]):
    def compose(self) -> ComposeResult:
        yield NewsBody("", id="body")


class _StubClick:
    def __init__(self, style: object) -> None:
        self.style = style

    def stop(self) -> None:
        pass


def _meta_style(item: NewsItem) -> object:
    from rich.text import Text

    text = Text()
    render_news_row(text, item, datetime.now(timezone.utc))
    return next(
        span.style
        for span in text.spans
        if not isinstance(span.style, str)
        and span.style.meta.get("news_url") is not None
    )


@pytest.mark.asyncio
async def test_clicking_title_opens_article() -> None:
    item = _item("https://example.com/article")
    app = _Harness()
    async with app.run_test():
        body = app.query_one("#body", NewsBody)
        with patch("goldsilver.widgets.news_panel.webbrowser.open") as mock_open:
            body.on_click(_StubClick(_meta_style(item)))

    mock_open.assert_called_once_with("https://example.com/article")


def test_malformed_url_gets_no_meta_span() -> None:
    from rich.text import Text

    item = _item("not-a-url")
    text = Text()
    render_news_row(text, item, datetime.now(timezone.utc))

    assert not any(
        not isinstance(span.style, str) and span.style.meta.get("news_url") is not None
        for span in text.spans
    )
