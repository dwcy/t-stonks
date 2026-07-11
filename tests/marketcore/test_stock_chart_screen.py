"""Mount-and-render smoke tests for the stock chart detail modal."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Button, Static

from marketcore.models import Bar
from marketcore.models_macro import DividendInfo
from marketcore.widgets.chart import PriceChart
from marketcore.widgets.daily_change_strip import DailyChangeStrip
from marketcore.widgets.stock_chart_screen import StockChartScreen


def _bars(n: int = 45) -> list[Bar]:
    base = datetime(2026, 5, 1, tzinfo=timezone.utc)
    return [
        Bar(
            symbol="NVDA",
            time=base + timedelta(days=i),
            open=100.0 + i,
            high=101.0 + i,
            low=99.0 + i,
            close=100.0 + i,
            volume=1000.0,
        )
        for i in range(n)
    ]


class _Harness(App[None]):
    def compose(self) -> ComposeResult:
        yield Static("base")


@pytest.mark.asyncio
async def test_modal_seeds_chart_and_strip() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        screen = StockChartScreen("NVDA", _bars())
        await app.push_screen(screen)
        await pilot.pause()

        chart = screen.query_one(PriceChart)
        strip = screen.query_one(DailyChangeStrip)
        assert len(chart._bars) == 45
        strip_text = str(strip.render())
        assert "%" in strip_text


@pytest.mark.asyncio
async def test_modal_seeds_chart_with_full_feature_parity() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        screen = StockChartScreen("NVDA", _bars())
        await app.push_screen(screen)
        await pilot.pause()

        chart = screen.query_one(PriceChart)
        assert chart._kind == "line"
        assert chart._show_sma is True
        assert chart._show_vwap is True
        assert chart._show_day_refs is True
        assert chart.mode == "history"
        bars = _bars()
        assert chart._prev_close == bars[-2].close
        assert chart._sess_high == bars[-1].high
        assert chart._sess_low == bars[-1].low


@pytest.mark.asyncio
async def test_modal_default_accent_color() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        screen = StockChartScreen("NVDA", _bars())
        await app.push_screen(screen)
        await pilot.pause()

        assert screen.query_one(PriceChart)._color == "#8ab4ff"


@pytest.mark.asyncio
async def test_modal_accepts_custom_accent_color() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        screen = StockChartScreen("NVDA", _bars(), accent_color=(155, 89, 255))
        await app.push_screen(screen)
        await pilot.pause()

        assert screen.query_one(PriceChart)._color == (155, 89, 255)


@pytest.mark.asyncio
async def test_modal_key_bindings_drive_chart_state() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        screen = StockChartScreen("NVDA", _bars())
        await app.push_screen(screen)
        await pilot.pause()

        chart = screen.query_one(PriceChart)
        assert chart.mode == "history"

        await pilot.press("h")
        await pilot.pause()
        assert chart.mode == "live"

        await pilot.press("x")
        await pilot.pause()
        assert chart._view.crosshair_active is True

        await pilot.press("left")
        await pilot.pause()
        assert chart._view.crosshair_index == len(chart._bars) - 2

        await pilot.press("enter")
        await pilot.pause()
        assert chart._view.crosshair_index in chart._view.pinned_indices

        await pilot.press("c")
        await pilot.pause()
        assert chart._view.pinned_indices == set()


@pytest.mark.asyncio
async def test_modal_handles_fewer_than_forty_days() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        screen = StockChartScreen("NVDA", _bars(5))
        await app.push_screen(screen)
        await pilot.pause()

        strip = screen.query_one(DailyChangeStrip)
        strip_text = str(strip.render())
        assert "No daily history" not in strip_text


@pytest.mark.asyncio
async def test_modal_handles_zero_bars_without_crashing() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        screen = StockChartScreen("NVDA", [])
        await app.push_screen(screen)
        await pilot.pause()

        strip = screen.query_one(DailyChangeStrip)
        assert "No daily history available." in str(strip.render())


@pytest.mark.asyncio
async def test_modal_shows_error_message_when_bars_empty() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        screen = StockChartScreen("NVDA", [])
        await app.push_screen(screen)
        await pilot.pause()

        error = screen.query_one("#stock-chart-error", Static)
        assert "Couldn't load chart data" in str(error.render())


@pytest.mark.asyncio
async def test_modal_omits_error_message_when_bars_present() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        screen = StockChartScreen("NVDA", _bars())
        await app.push_screen(screen)
        await pilot.pause()

        assert len(screen.query("#stock-chart-error")) == 0


@pytest.mark.asyncio
async def test_retry_action_invokes_callback() -> None:
    calls: list[bool] = []
    app = _Harness()
    async with app.run_test() as pilot:
        screen = StockChartScreen("NVDA", [], on_retry=lambda: calls.append(True))
        await app.push_screen(screen)
        await pilot.pause()

        await pilot.press("r")
        await pilot.pause()

        assert calls == [True]


@pytest.mark.asyncio
async def test_apply_bars_clears_error_and_reseeds_chart() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        screen = StockChartScreen("NVDA", [])
        await app.push_screen(screen)
        await pilot.pause()
        assert len(screen.query("#stock-chart-error")) == 1

        screen.apply_bars(_bars())
        await pilot.pause()

        assert len(screen.query("#stock-chart-error")) == 0
        assert len(screen.query_one(PriceChart)._bars) == 45


@pytest.mark.asyncio
async def test_apply_bars_keeps_error_when_retry_still_empty() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        screen = StockChartScreen("NVDA", [])
        await app.push_screen(screen)
        await pilot.pause()

        screen.apply_bars([])
        await pilot.pause()

        assert len(screen.query("#stock-chart-error")) == 1


@pytest.mark.asyncio
async def test_close_button_dismisses() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        screen = StockChartScreen("NVDA", _bars())
        await app.push_screen(screen)
        await pilot.pause()
        await pilot.click("#stock-chart-close")
        await pilot.pause()

        assert not isinstance(app.screen, StockChartScreen)


@pytest.mark.asyncio
async def test_report_section_omitted_when_not_watchlisted() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        screen = StockChartScreen("NVDA", _bars())
        await app.push_screen(screen)
        await pilot.pause()

        assert len(screen.query("#stock-chart-report")) == 0
        assert len(screen.query("#stock-chart-open-report")) == 0


@pytest.mark.asyncio
async def test_report_section_shown_with_next_run_and_latest_summary() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        screen = StockChartScreen(
            "NVDA",
            _bars(),
            next_report_at=datetime(2026, 6, 10, 14, 0, tzinfo=timezone.utc),
            latest_report_summary="09:00  SUCCESS",
            latest_report_path="file:///tmp/report.html",
        )
        await app.push_screen(screen)
        await pilot.pause()

        report_text = str(screen.query_one("#stock-chart-report", Static).render())
        assert "14:00" in report_text
        assert "09:00" in report_text
        assert "SUCCESS" in report_text
        assert len(screen.query("#stock-chart-open-report")) == 1


@pytest.mark.asyncio
async def test_open_report_button_opens_browser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened: list[str] = []
    from marketcore.widgets import stock_chart_screen

    monkeypatch.setattr(stock_chart_screen.webbrowser, "open", opened.append)

    app = _Harness()
    async with app.run_test() as pilot:
        screen = StockChartScreen(
            "NVDA",
            _bars(),
            latest_report_summary="09:00  SUCCESS",
            latest_report_path="file:///tmp/report.html",
        )
        await app.push_screen(screen)
        await pilot.pause()
        await pilot.click("#stock-chart-open-report")
        await pilot.pause()

    assert opened == ["file:///tmp/report.html"]


@pytest.mark.asyncio
async def test_dividend_section_shows_last_payment() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        screen = StockChartScreen(
            "NVDA",
            _bars(),
            dividend=DividendInfo(
                ticker="NVDA",
                amount=0.24,
                payment_date=date(2026, 6, 1),
                is_forward_looking=False,
            ),
        )
        await app.push_screen(screen)
        await pilot.pause()

        text = str(screen.query_one("#stock-chart-dividend", Static).render())
        assert "Last payment" in text
        assert "2026-06-01" in text
        assert "0.2400" in text


@pytest.mark.asyncio
async def test_dividend_section_shows_unavailable_state() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        screen = StockChartScreen("NVDA", _bars(), dividend=None)
        await app.push_screen(screen)
        await pilot.pause()

        text = str(screen.query_one("#stock-chart-dividend", Static).render())
        assert "no dividend information available" in text
