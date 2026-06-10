"""Tests for prompt template loading + placeholder substitution."""

from __future__ import annotations

import re
from datetime import datetime

from goldsilver.data.session import STOCKHOLM
from goldsilver.reports.models import ReportTicker
from goldsilver.reports.prompt_builder import AnalysisPromptContext, build_prompt

_KNOWN_TOKENS = [
    "{TICKER}",
    "{TICKER_LABEL}",
    "{TICKER_KIND}",
    "{STOCKHOLM_TIME}",
    "{DATE}",
    "{SWEDISH_PHASE}",
    "{US_MARKET_STATE}",
    "{REFERENCE_QUOTE}",
]


def _prompt_for(ticker: ReportTicker, reference_quote: str | None = None) -> str:
    now = datetime(2026, 6, 8, 15, 35, tzinfo=STOCKHOLM)
    ctx = AnalysisPromptContext.for_ticker(ticker, now, reference_quote=reference_quote)
    return build_prompt(ctx)


def test_all_placeholders_substituted() -> None:
    prompt = _prompt_for(ReportTicker.metal("XAU"))
    for token in _KNOWN_TOKENS:
        assert token not in prompt, f"{token} left unsubstituted"


def test_version_line_stripped() -> None:
    prompt = _prompt_for(ReportTicker.stock("NVDA"))
    assert "TEMPLATE_VERSION" not in prompt
    assert prompt.lstrip().startswith("You are a professional")


def test_context_values_present() -> None:
    prompt = _prompt_for(ReportTicker.metal("XAU"))
    assert "Gold (XAU)" in prompt
    assert "2026-06-08 15:35" in prompt
    assert "US_INFLUENCE" in prompt  # 15:35 Stockholm phase
    assert "OPENING" in prompt  # 09:35 ET


def test_reference_quote_injected() -> None:
    quote_line = (
        "Last price for LUG.ST: **515.60 SEK** (previous close 524.00, -1.60%)."
    )
    prompt = _prompt_for(ReportTicker.stock("LUG.ST"), reference_quote=quote_line)
    assert quote_line in prompt
    assert "Ground Truth" in prompt


def test_reference_quote_fallback_when_missing() -> None:
    prompt = _prompt_for(ReportTicker.stock("LUG.ST"))
    assert "No reference quote available" in prompt


def test_stock_kind_framing() -> None:
    prompt = _prompt_for(ReportTicker.stock("NVDA"))
    assert "NVDA" in prompt
    # The literal JSON braces in the output-format example survive (not treated as tokens).
    assert "VERDICT:" in prompt
    assert re.search(r'"intraday"', prompt)
