"""Price-level alert engine: fires once per crossing, re-arming on the opposite side."""

from __future__ import annotations


class PriceAlertEngine:
    def __init__(self) -> None:
        self._above: dict[tuple[str, float], bool] = {}

    def check(
        self, symbol: str, price: float, levels: list[float]
    ) -> list[tuple[float, bool]]:
        """Return (level, crossed_up) for every level the price just crossed.

        The first observation per level only arms the engine — no alert fires
        until the price actually moves to the other side of the level.
        """
        fired: list[tuple[float, bool]] = []
        for level in levels:
            above = price >= level
            key = (symbol, level)
            prev = self._above.get(key)
            self._above[key] = above
            if prev is not None and prev != above:
                fired.append((level, above))
        return fired

    def forget(self, symbol: str, level: float) -> None:
        self._above.pop((symbol, level), None)
