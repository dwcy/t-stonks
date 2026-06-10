"""Score historical strategy signals against the forward price move."""

from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass
from datetime import timedelta, timezone

from goldsilver.data.models import Bar
from goldsilver.data.signal_strategies import STRATEGY_REGISTRY, SignalStrategy

DEFAULT_HORIZON_MINUTES = 30


@dataclass(slots=True)
class StrategyScore:
    strategy: str
    kind: str
    fires: int
    scored: int
    wins: int

    @property
    def win_rate(self) -> float | None:
        if self.scored == 0:
            return None
        return self.wins / self.scored * 100.0


def score_signals(
    bars: list[Bar],
    strategy: SignalStrategy,
    symbol: str,
    *,
    horizon: timedelta,
) -> StrategyScore:
    times = [b.time.astimezone(timezone.utc) for b in bars]
    fires: list[tuple[int, str]] = []
    for i, bar in enumerate(bars):
        sig = strategy.observe(symbol, bar.close, bar.time)
        # Cooldowns re-emit the last fired signal; only count fresh fires.
        if sig.action in ("BUY", "SELL") and sig.at == times[i]:
            fires.append((i, sig.action))
    wins = scored = 0
    for i, action in fires:
        target = times[i] + horizon
        k = bisect_left(times, target)
        if k >= len(bars):
            continue
        entry = bars[i].close
        forward = bars[k].close
        scored += 1
        if (action == "BUY" and forward > entry) or (
            action == "SELL" and forward < entry
        ):
            wins += 1
    return StrategyScore(
        strategy=strategy.name,
        kind=strategy.kind,
        fires=len(fires),
        scored=scored,
        wins=wins,
    )


def score_all(
    bars_by_symbol: dict[str, list[Bar]],
    param_overrides: dict[str, dict[str, float]],
    *,
    horizon_minutes: int = DEFAULT_HORIZON_MINUTES,
) -> dict[str, dict[str, StrategyScore]]:
    horizon = timedelta(minutes=horizon_minutes)
    out: dict[str, dict[str, StrategyScore]] = {}
    for symbol, bars in bars_by_symbol.items():
        per_symbol: dict[str, StrategyScore] = {}
        for cls in STRATEGY_REGISTRY:
            strategy = cls()
            for key, value in param_overrides.get(strategy.name, {}).items():
                strategy.set_param(key, value)
            per_symbol[strategy.name] = score_signals(
                bars, strategy, symbol, horizon=horizon
            )
        out[symbol] = per_symbol
    return out
