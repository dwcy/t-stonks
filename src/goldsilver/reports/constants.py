"""Shared constants for the report engine: pinned metals, defaults, filename rules."""

from __future__ import annotations

from typing import Final


PINNED_METALS: Final[tuple[str, ...]] = ("XAU", "XAG")
PINNED_COMMODITIES: Final[tuple[str, ...]] = ("BRENT", "COPPER")

# Despite the name, this also covers the pinned commodities (report titles/labels
# use one shared symbol->readable-name lookup regardless of instrument kind).
METAL_LABELS: Final[dict[str, str]] = {
    "XAU": "Gold",
    "XAG": "Silver",
    "BRENT": "Oil",
    "COPPER": "Copper",
}

DEFAULT_ALLOWED_TOOLS: Final[tuple[str, ...]] = ("WebSearch", "WebFetch", "Read")

KNOWN_TOOLS: Final[frozenset[str]] = frozenset(
    {"WebSearch", "WebFetch", "Read", "Grep", "Glob"}
)

TEMPLATE_VERSION: Final[int] = 1

DEFAULT_INTERVAL_MINUTES: Final[int] = 60
DEFAULT_TIMEOUT_SECONDS: Final[int] = 360
DEFAULT_MAX_CONCURRENCY: Final[int] = 3
DEFAULT_OUT_DIR: Final[str] = "reports"

INTERVAL_BOUNDS: Final[tuple[int, int]] = (15, 1440)
TIMEOUT_BOUNDS: Final[tuple[int, int]] = (30, 900)
CONCURRENCY_BOUNDS: Final[tuple[int, int]] = (1, 8)

_FILENAME_TRANSLATION: Final[dict[int, str]] = str.maketrans(
    {"/": "-", ".": "-", " ": "-", ":": "-"}
)


def safe_name(symbol: str) -> str:
    """Symbol → filesystem-safe token: uppercased with / . space : replaced by -."""
    return symbol.upper().translate(_FILENAME_TRANSLATION)
