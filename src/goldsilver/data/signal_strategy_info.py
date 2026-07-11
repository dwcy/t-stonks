"""Plain-language descriptions and relative priority for each signal strategy.

Keyed by the same `SignalStrategy.name` strings as `signal_strategies.STRATEGY_REGISTRY`,
kept in a sibling module so this static descriptive content doesn't compound the
already-oversized `signal_strategies.py` (justified at that file's line 1).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IndicatorInfo:
    short_label: str
    description: str
    priority_rank: int
    rationale: str


# Ranked by signal character: confirmed/slower signals (longer averaging window,
# fewer false triggers) outrank fast/noisier ones (short window, prone to whipsaw).
INDICATOR_INFO: dict[str, IndicatorInfo] = {
    "Z-Score Recoil": IndicatorInfo(
        short_label="Z",
        description=(
            "How many standard deviations price has moved from its recent mean — "
            "flags statistical extremes likely to snap back toward average."
        ),
        priority_rank=1,
        rationale=(
            "Confirms over the same window as MACD and only fires on genuine "
            "statistical extremes, so it produces the fewest false signals of the six."
        ),
    ),
    "MACD Momentum": IndicatorInfo(
        short_label="MACD",
        description=(
            "The gap between a fast and slow moving average — widening signals a "
            "trend building, narrowing signals it fading."
        ),
        priority_rank=2,
        rationale=(
            "Smooths over a long EMA window, trading a little lag for a low "
            "false-signal rate — ranks just behind Z-Score."
        ),
    ),
    "Bollinger Recoil": IndicatorInfo(
        short_label="BB",
        description=(
            "Flags when price touches the outer edge of its recent volatility "
            "band, expecting a snap-back toward the middle."
        ),
        priority_rank=3,
        rationale=(
            "Reacts faster than MACD/Z-Score since it only needs the current "
            "volatility band, but is more prone to false signals in a strong trend."
        ),
    ),
    "RSI Recoil": IndicatorInfo(
        short_label="RSI",
        description=(
            "A bounded 0-100 oscillator comparing recent gains to losses — "
            "extreme readings suggest overbought/oversold conditions."
        ),
        priority_rank=4,
        rationale=(
            "Smoothed over its period but reacts to shorter-term swings than the "
            "band/MACD pair above, so it ranks below them."
        ),
    ),
    "ROC Momentum": IndicatorInfo(
        short_label="ROC",
        description=(
            "The raw percentage price change over the last 2 minutes — a direct "
            "read of how fast price is moving right now."
        ),
        priority_rank=5,
        rationale=(
            "Unsmoothed and very short-window, so it reacts almost instantly but "
            "is the second-noisiest of the six."
        ),
    ),
    "Slope Momentum": IndicatorInfo(
        short_label="Slope",
        description=(
            "Fits a line through the most recent ticks to gauge the immediate "
            "direction and steepness of the move."
        ),
        priority_rank=6,
        rationale=(
            "The fastest-reacting and noisiest signal — most prone to whipsaw on "
            "random tick noise, so it ranks last."
        ),
    ),
}

INDICATOR_PRIORITY_ORDER: tuple[str, ...] = tuple(
    sorted(INDICATOR_INFO, key=lambda name: INDICATOR_INFO[name].priority_rank)
)
