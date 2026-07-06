"""QuantumSettings — per-app persisted watchlists, isolated under the quantum config dir."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field

from marketcore import paths as marketcore_paths
from marketcore.fsutil import atomic_write_text

from quantum.data.presets import DEFAULT_ACCENT, ETF_DEFAULTS, PUREPLAY_DEFAULTS

APP_NAME = "quantum"


def settings_path():
    return marketcore_paths.settings_path(APP_NAME)


@dataclass
class QuantumSettings:
    etf_tickers: list[str] = field(default_factory=lambda: list(ETF_DEFAULTS))
    stock_tickers: list[str] = field(default_factory=lambda: list(PUREPLAY_DEFAULTS))
    news_enabled: bool = True
    accent_color_name: str = DEFAULT_ACCENT
    refresh_interval_s: float = 60.0

    @classmethod
    def load(cls) -> QuantumSettings:
        path = settings_path()
        if not path.exists():
            return cls()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls()
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in raw.items() if k in known})

    def save(self) -> None:
        path = settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(asdict(self), indent=2))
