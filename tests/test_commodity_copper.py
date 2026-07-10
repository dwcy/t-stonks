"""Copper must come from Avanza (USD/tonne) so it matches the Avanza app, not COMEX USD/lb."""

from __future__ import annotations

import pytest

from goldsilver.data import commodity_service
from goldsilver.data.commodity_service import fetch_commodity_quote

_PAYLOAD = {
    "name": "Koppar",
    "quote": {"last": 13670.0, "highest": 13800.0, "lowest": 13600.0},
    "historicalClosingPrices": {"oneDay": 13731.0},
}


class _FakeResponse:
    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return _PAYLOAD


class _FakeClient:
    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    async def __aenter__(self) -> "_FakeClient":
        return self

    async def __aexit__(self, *args: object) -> bool:
        return False

    async def get(self, url: str) -> _FakeResponse:
        return _FakeResponse()


@pytest.mark.asyncio
async def test_copper_reads_avanza_quote(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(commodity_service.httpx, "AsyncClient", _FakeClient)

    quote = await fetch_commodity_quote("COPPER")

    assert quote is not None
    assert quote.symbol == "COPPER"
    assert quote.price == 13670.0
    assert quote.previous_close == 13731.0
    assert quote.change_percent < 0
