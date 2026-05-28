"""Smoke test: verify Avanza GOLDSP / SILVERSP feed + Tick emission."""

from __future__ import annotations

import asyncio

from goldsilver.data import MetalsService, Tick
from goldsilver.data.models import GOLD, SILVER


async def main() -> None:
    seen: list[Tick] = []

    async def on_tick(tick: Tick) -> None:
        seen.append(tick)
        print(
            f"{tick.time.isoformat()} {tick.symbol:5} "
            f"price={tick.price:>10.4f} "
            f"chg={tick.change:+8.4f} ({tick.change_percent:+.3f}%) "
            f"hi={tick.day_high:.4f} lo={tick.day_low:.4f}"
        )

    async def on_status(status: str) -> None:
        print(f"[status] {status}")

    service = MetalsService(tick_handler=on_tick, status_handler=on_status)
    service.start()
    try:
        await asyncio.sleep(20)
    finally:
        await service.stop()

    gold_ticks = [t for t in seen if t.symbol == GOLD]
    silver_ticks = [t for t in seen if t.symbol == SILVER]
    print(f"\n[done] gold ticks={len(gold_ticks)} silver ticks={len(silver_ticks)}")


if __name__ == "__main__":
    asyncio.run(main())
