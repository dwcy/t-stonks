"""Every strategy must have descriptive info with a unique, contiguous priority rank."""

from __future__ import annotations

from goldsilver.data.signal_strategies import STRATEGY_NAMES
from goldsilver.data.signal_strategy_info import (
    INDICATOR_INFO,
    INDICATOR_PRIORITY_ORDER,
)


def test_every_strategy_has_indicator_info() -> None:
    assert set(INDICATOR_INFO) == set(STRATEGY_NAMES)


def test_priority_ranks_are_unique_and_contiguous() -> None:
    ranks = sorted(info.priority_rank for info in INDICATOR_INFO.values())

    assert ranks == list(range(1, len(INDICATOR_INFO) + 1))


def test_priority_order_matches_z_score_first_slope_last() -> None:
    assert INDICATOR_PRIORITY_ORDER[0] == "Z-Score Recoil"
    assert INDICATOR_PRIORITY_ORDER[-1] == "Slope Momentum"


def test_every_info_has_nonempty_description_and_rationale() -> None:
    for info in INDICATOR_INFO.values():
        assert info.description.strip()
        assert info.rationale.strip()
        assert info.short_label.strip()
