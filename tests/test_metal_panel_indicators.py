"""Indicator badges render in priority order and toggle a description on click."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Static

from goldsilver.data.signal_strategy_info import INDICATOR_PRIORITY_ORDER
from goldsilver.widgets.metal_panel import MetalPanel


class _Harness(App[None]):
    def compose(self) -> ComposeResult:
        yield MetalPanel("XAU", "GOLD", accent_color="#ffd56b")


class _StubClick:
    def __init__(self, style: object) -> None:
        self.style = style

    def stop(self) -> None:
        pass


def _meta_style(rendered: object, key: str) -> object:
    return next(
        span.style
        for span in rendered.spans  # type: ignore[attr-defined]
        if not isinstance(span.style, str) and span.style.meta.get("indicator") == key
    )


@pytest.mark.asyncio
async def test_badges_render_in_priority_order() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        panel = app.query_one(MetalPanel)
        panel.set_visible_signals(["Slope Momentum", "Z-Score Recoil", "RSI Recoil"])
        panel.price = 100.0
        await pilot.pause()
        rendered = app.query_one("#change-row", Static).render()

    plain = str(rendered)
    z_pos = plain.index("Z ")
    rsi_pos = plain.index("RSI ")
    slope_pos = plain.index("Slope ")
    assert z_pos < rsi_pos < slope_pos
    assert INDICATOR_PRIORITY_ORDER.index("Z-Score Recoil") == 0


@pytest.mark.asyncio
async def test_clicking_badge_shows_and_hides_description() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        panel = app.query_one(MetalPanel)
        panel.set_visible_signals(["Z-Score Recoil"])
        panel.price = 100.0
        await pilot.pause()
        row = app.query_one("#change-row", Static)
        style = _meta_style(row.render(), "Z-Score Recoil")

        row.on_click(_StubClick(style))
        await pilot.pause()
        detail = str(app.query_one("#indicator-detail", Static).render())
        assert "Z-Score Recoil" in detail
        assert panel.expanded_indicator == "Z-Score Recoil"

        row.on_click(_StubClick(style))
        await pilot.pause()
        detail_after = str(app.query_one("#indicator-detail", Static).render())
        assert panel.expanded_indicator is None
        assert "Z-Score Recoil" not in detail_after


@pytest.mark.asyncio
async def test_toggling_description_does_not_alter_signal_values() -> None:
    app = _Harness()
    async with app.run_test() as pilot:
        panel = app.query_one(MetalPanel)
        panel.set_visible_signals(["Z-Score Recoil"])
        from goldsilver.data.models_macro import Signal

        sig = Signal(
            symbol="XAU",
            strategy="Z-Score Recoil",
            kind="recoil",
            action="BUY",
            intensity_sigma=2.5,
            reason="z +2.5",
            at=datetime.now(timezone.utc),
        )
        panel.apply_signal(sig)
        panel.price = 100.0
        await pilot.pause()
        row = app.query_one("#change-row", Static)
        style = _meta_style(row.render(), "Z-Score Recoil")

        row.on_click(_StubClick(style))
        await pilot.pause()

        assert panel._signals["Z-Score Recoil"] is sig
