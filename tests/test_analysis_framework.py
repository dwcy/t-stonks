"""Tests that the prompt template encodes the assumption-testing framework + verdict."""

from __future__ import annotations

from pathlib import Path

from goldsilver.reports.claude_runner import parse_verdict

_TEMPLATE = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "goldsilver"
    / "reports"
    / "prompts"
    / "analysis_prompt.md"
).read_text("utf-8")


def test_market_reaction_validation_is_highest_priority() -> None:
    assert "Market Reaction Validation — HIGHEST PRIORITY" in _TEMPLATE
    assert "Observed price action always overrides theory" in _TEMPLATE
    assert "CONFIRMED / CONTRADICTED" in _TEMPLATE


def test_enhancement_sections_present() -> None:
    for heading in (
        "Market Regime Detection",
        "Correlation Validation",
        "European influence",
        "Bond market",
        "Capital / sector flow",
        "Positioning & breadth",
        "Scenario Analysis",
        "Next Catalyst",
        "Trade-Timing Assessment",
    ):
        assert heading in _TEMPLATE, f"missing framework section: {heading}"


def test_scenario_probabilities_sum_constraint() -> None:
    assert "probabilities must total 100%" in _TEMPLATE


def test_version_and_placeholders_present() -> None:
    assert _TEMPLATE.splitlines()[0].startswith("<!-- TEMPLATE_VERSION:")
    for token in (
        "{TICKER}",
        "{SWEDISH_PHASE}",
        "{US_MARKET_STATE}",
        "{STOCKHOLM_TIME}",
    ):
        assert token in _TEMPLATE


def test_verdict_example_parses() -> None:
    sample = (
        '<!-- VERDICT: {"intraday":"SELL","swing":"HOLD","confidence":40,'
        '"swedish_phase":"US_INFLUENCE","us_state":"OPEN","usd_impact":"Negative",'
        '"gold_impact":"Positive","news_impact":"Neutral","geopolitical_impact":"Positive",'
        '"top_reasons":["a","b","c"],"what_would_change":["y"]} -->'
    )
    verdict = parse_verdict(sample)
    assert verdict is not None
    assert verdict.intraday == "SELL"
    assert verdict.gold_impact == "Positive"
