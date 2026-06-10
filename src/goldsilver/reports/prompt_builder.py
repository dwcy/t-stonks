"""Build the analysis prompt by substituting per-run context into the template asset."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from goldsilver.data.session import STOCKHOLM
from goldsilver.reports.models import ReportTicker
from goldsilver.reports.phase import swedish_phase, us_market_state

_TEMPLATE_PATH = Path(__file__).parent / "prompts" / "analysis_prompt.md"
_VERSION_PREFIX = "<!-- TEMPLATE_VERSION:"


_NO_QUOTE_FALLBACK = (
    "No reference quote available for this run. Verify the exchange suffix and "
    "currency of the exact listing with extra care before quoting any price."
)


@dataclass(slots=True)
class AnalysisPromptContext:
    ticker: str
    ticker_label: str
    ticker_kind: str
    stockholm_time: str
    date: str
    swedish_phase: str
    us_market_state: str
    reference_quote: str = _NO_QUOTE_FALLBACK

    @classmethod
    def for_ticker(
        cls,
        ticker: ReportTicker,
        now_local: datetime,
        *,
        reference_quote: str | None = None,
    ) -> "AnalysisPromptContext":
        local = now_local.astimezone(STOCKHOLM)
        return cls(
            ticker=ticker.symbol,
            ticker_label=ticker.label,
            ticker_kind=ticker.kind,
            stockholm_time=local.strftime("%Y-%m-%d %H:%M"),
            date=local.strftime("%Y-%m-%d"),
            swedish_phase=swedish_phase(local).value,
            us_market_state=us_market_state(local).value,
            reference_quote=reference_quote or _NO_QUOTE_FALLBACK,
        )

    def _replacements(self) -> dict[str, str]:
        return {
            "{TICKER}": self.ticker,
            "{TICKER_LABEL}": self.ticker_label,
            "{TICKER_KIND}": self.ticker_kind,
            "{STOCKHOLM_TIME}": self.stockholm_time,
            "{DATE}": self.date,
            "{SWEDISH_PHASE}": self.swedish_phase,
            "{US_MARKET_STATE}": self.us_market_state,
            "{REFERENCE_QUOTE}": self.reference_quote,
        }


@lru_cache(maxsize=1)
def _load_template() -> str:
    text = _TEMPLATE_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()
    if lines and lines[0].startswith(_VERSION_PREFIX):
        lines = lines[1:]
    return "\n".join(lines).lstrip("\n")


def build_prompt(context: AnalysisPromptContext) -> str:
    prompt = _load_template()
    for token, value in context._replacements().items():
        prompt = prompt.replace(token, value)
    return prompt
