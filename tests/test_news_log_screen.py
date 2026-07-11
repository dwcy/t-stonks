"""Smoke tests for the news log modal."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from goldsilver.data.models_macro import NewsItem
from goldsilver.widgets.news_log_screen import NewsLogScreen


def _item(url: str) -> NewsItem:
    return NewsItem(
        source="REUTERS",
        title=f"Headline {url}",
        url=url,
        published=datetime.now(timezone.utc),
    )


class _Harness(App[None]):
    def compose(self) -> ComposeResult:
        yield Static("base")


@pytest.mark.asyncio
async def test_empty_history_shows_placeholder() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        screen = NewsLogScreen(())
        await app.push_screen(screen)
        await pilot.pause()
        body = str(screen.query_one("#news-log-text", Static).render())

    assert "No history yet." in body


@pytest.mark.asyncio
async def test_history_items_are_listed() -> None:
    items = (_item("https://e/1"), _item("https://e/2"))
    app = _Harness()
    async with app.run_test() as pilot:
        screen = NewsLogScreen(items)
        await app.push_screen(screen)
        await pilot.pause()
        body = str(screen.query_one("#news-log-text", Static).render())

    assert "Headline https://e/1" in body
    assert "Headline https://e/2" in body


@pytest.mark.asyncio
async def test_close_button_dismisses() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        screen = NewsLogScreen(())
        await app.push_screen(screen)
        await pilot.pause()
        await pilot.click("#news-log-close")
        await pilot.pause()

        assert not isinstance(app.screen, NewsLogScreen)
