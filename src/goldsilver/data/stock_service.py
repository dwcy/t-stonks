"""Facade: StockService relocated to marketcore; registers goldsilver display names."""

from __future__ import annotations

from marketcore.services.stock_service import (
    MAX_SPARK_POINTS,
    STOCK_REFRESH_INTERVAL_S,
    StockService,
    _NAME_CACHE,
    _resolve_display_name,
    fetch_single_quote,
    register_names,
    yf,
)

from goldsilver.data.stock_presets import NAME_OVERRIDES, PRESET_NAMES

register_names(PRESET_NAMES)
register_names(NAME_OVERRIDES)

__all__ = [
    "MAX_SPARK_POINTS",
    "STOCK_REFRESH_INTERVAL_S",
    "StockService",
    "fetch_single_quote",
]
