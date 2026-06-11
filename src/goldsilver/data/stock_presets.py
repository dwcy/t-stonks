"""Default stock watchlist presets: OMXS30 constituents plus hand-picked Stockholm extras."""

from __future__ import annotations

# OMXS30 composition as of the Dec 2025 index review (Yahoo Finance tickers).
PRESET_STOCKS: tuple[tuple[str, str], ...] = (
    ("ABB.ST", "ABB"),
    ("ADDT-B.ST", "Addtech B"),
    ("ALFA.ST", "Alfa Laval"),
    ("ASSA-B.ST", "Assa Abloy B"),
    ("ATCO-A.ST", "Atlas Copco A"),
    ("AZN.ST", "AstraZ"),
    ("BOL.ST", "Boliden"),
    ("EPI-A.ST", "Epiroc A"),
    ("EQT.ST", "EQT"),
    ("ERIC-B.ST", "Ericsson"),
    ("ESSITY-B.ST", "Essity B"),
    ("EVO.ST", "Evolution"),
    ("HEXA-B.ST", "Hexagon B"),
    ("HM-B.ST", "Hennes & Mauritz B"),
    ("INDU-C.ST", "IndstriVrdn"),
    ("INVE-B.ST", "Investor B"),
    ("LIFCO-B.ST", "Lifco B"),
    ("NDA-SE.ST", "Nordea Bank"),
    ("NIBE-B.ST", "Nibe"),
    ("SAAB-B.ST", "Saab"),
    ("SAND.ST", "Sandvik"),
    ("SCA-B.ST", "SCA B"),
    ("SEB-A.ST", "SEB A"),
    ("SHB-A.ST", "Handelsbanken A"),
    ("SKA-B.ST", "Skanska B"),
    ("SKF-B.ST", "SKF B"),
    ("SWED-A.ST", "Swedbank"),
    ("TEL2-B.ST", "Tele2 B"),
    ("TELIA.ST", "Telia"),
    ("VOLV-B.ST", "Volvo"),
    ("RUSTA.ST", "Rusta"),
    ("CLA-B.ST", "Cloetta"),
    ("SBB-B.ST", "SBB B"),
    ("BURE.ST", "Bure Equity"),
    ("KINV-B.ST", "Kinnevik"),
    ("VSURE.ST", "Verisure"),
    ("SINCH.ST", "Sinch"),
)

PRESET_TICKERS: frozenset[str] = frozenset(t for t, _ in PRESET_STOCKS)

PRESET_NAMES: dict[str, str] = dict(PRESET_STOCKS)

# Display-name overrides for non-preset tickers (skips the Yahoo shortName lookup).
NAME_OVERRIDES: dict[str, str] = {
    "LUG.TO": "Lundin Gold",
    "LUG.ST": "Lundin Gold",
    "LUMI.ST": "Lundin Mining",
    "LUNR.V": "LUNR",
}


def extra_row_tickers(
    enabled_presets: list[str],
    extra_tickers: list[str],
    exclude: list[str] | None = None,
) -> list[str]:
    excluded = set(exclude or [])
    out: list[str] = []
    for ticker, _ in PRESET_STOCKS:
        if ticker in enabled_presets and ticker not in excluded:
            out.append(ticker)
            excluded.add(ticker)
    for ticker in extra_tickers:
        if ticker not in excluded:
            out.append(ticker)
            excluded.add(ticker)
    return out
