"""Smoke test for TradeSimulatorScreen mount and render."""

from __future__ import annotations

import pytest

from goldsilver.app import GoldSilverApp
from goldsilver.widgets.trade_simulator import TradeSimulatorScreen


@pytest.mark.asyncio
async def test_screen_mounts_with_core_widgets() -> None:
    app = GoldSilverApp()
    async with app.run_test(size=(140, 50)) as pilot:
        await pilot.pause()
        await pilot.pause()
        await app.action_trade_simulator()
        await pilot.pause()
        await pilot.pause()
        screen = app.screen
        assert isinstance(screen, TradeSimulatorScreen)
        for wid in (
            "#trade-sim-dialog",
            "#trade-sim-title",
            "#sim-cash",
            "#sim-today",
            "#sim-lifetime",
            "#sim-status",
            "#sim-trades",
            "#sim-enabled",
            "#sim-close",
            "#sim-liquidate",
            "#sim-reset",
        ):
            assert screen.query(wid), f"missing widget {wid}"
