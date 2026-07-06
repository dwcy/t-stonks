"""Default quantum watchlists, display names, and accent colours."""

from __future__ import annotations

# Headline ETF tiles (Defiance Quantum ETF + a quantum-adjacent thematic ETF).
ETF_DEFAULTS: tuple[str, ...] = ("QTUM", "ARKQ")

# Pure-play quantum-computing stocks rendered as a tile grid.
PUREPLAY_DEFAULTS: tuple[str, ...] = (
    "IONQ",
    "RGTI",
    "QUBT",
    "QBTS",
    "ARQQ",
    "LAES",
    "QMCO",
    "QSI",
)

ACCENT_PRESETS: dict[str, tuple[int, int, int]] = {
    "quantum-violet": (155, 89, 255),
    "quantum-cyan": (0, 200, 220),
    "quantum-amber": (255, 191, 0),
}
DEFAULT_ACCENT = "quantum-violet"

NAME_OVERRIDES: dict[str, str] = {
    "QTUM": "Defiance Quantum ETF",
    "ARKQ": "ARK Autonomous & Robotics",
    "IONQ": "IonQ",
    "RGTI": "Rigetti Computing",
    "QUBT": "Quantum Computing Inc",
    "QBTS": "D-Wave Quantum",
    "ARQQ": "Arqit Quantum",
    "LAES": "SEALSQ",
    "QMCO": "Quantum Corp",
    "QSI": "Quantum-Si",
}
