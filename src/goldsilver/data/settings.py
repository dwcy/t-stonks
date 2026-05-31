from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Literal


ChartKind = Literal["line", "candle"]
ChartZoom = Literal["24h", "3h", "1h"]
ChartMode = Literal["live", "history"]
SignalMode = Literal["MOMENTUM", "RECOIL", "OFF"]  # legacy; ignored at runtime


CHART_ZOOM_CHOICES: tuple[ChartZoom, ...] = ("24h", "3h", "1h")
CHART_MODE_CHOICES: tuple[ChartMode, ...] = ("live", "history")


def _default_stock_tickers() -> list[str]:
    return ["LUG.TO", "LUG.ST", "LUMI.ST", "LUNR.V"]


GOLD_PRESETS: dict[str, tuple[int, int, int]] = {
    "Classic Gold": (255, 213, 107),
    "Deep Gold": (212, 175, 55),
    "Amber": (255, 165, 30),
    "Copper": (184, 115, 51),
    "Lemon": (255, 240, 100),
}

SILVER_PRESETS: dict[str, tuple[int, int, int]] = {
    "Pearl": (208, 208, 224),
    "Platinum": (229, 228, 226),
    "Steel": (160, 175, 200),
    "Slate": (180, 188, 205),
    "Frost": (200, 220, 240),
}

DEFAULT_GOLD = "Classic Gold"
DEFAULT_SILVER = "Pearl"


METALS_COLUMNS_CHOICES: tuple[int, ...] = (1, 2, 3, 4)


def _default_visible_signals() -> dict[str, bool]:
    from goldsilver.data.signal_strategies import (
        DEFAULT_VISIBLE,
        STRATEGY_NAMES,
    )

    return {name: (name in DEFAULT_VISIBLE) for name in STRATEGY_NAMES}


def _default_signal_params() -> dict[str, dict[str, float]]:
    return {}


@dataclass(slots=True)
class AppSettings:
    timeframe_index: int = 0
    chart_kind: ChartKind = "line"
    chart_zoom: ChartZoom = "24h"
    chart_mode: ChartMode = "live"
    show_sma: bool = False
    show_vwap: bool = False
    show_day_refs: bool = False
    signal_mode: SignalMode = "MOMENTUM"
    show_news_markets: bool = True
    show_news_trump: bool = True
    gold_color_name: str = DEFAULT_GOLD
    silver_color_name: str = DEFAULT_SILVER
    metals_columns: int = 2
    stock_tickers: list[str] = field(default_factory=_default_stock_tickers)
    visible_signals: dict[str, bool] = field(
        default_factory=_default_visible_signals
    )
    signal_params: dict[str, dict[str, float]] = field(
        default_factory=_default_signal_params
    )
    marker_momentum_strategy: str = ""
    marker_recoil_strategy: str = ""

    def __post_init__(self) -> None:
        if self.metals_columns not in METALS_COLUMNS_CHOICES:
            self.metals_columns = 2
        if self.chart_zoom not in CHART_ZOOM_CHOICES:
            self.chart_zoom = "24h"
        if self.chart_mode not in CHART_MODE_CHOICES:
            self.chart_mode = "live"
        if not isinstance(self.stock_tickers, list):
            self.stock_tickers = _default_stock_tickers()
        else:
            cleaned: list[str] = []
            seen: set[str] = set()
            for raw in self.stock_tickers:
                if not isinstance(raw, str):
                    continue
                t = raw.strip()
                if not t or t in seen:
                    continue
                seen.add(t)
                cleaned.append(t)
            self.stock_tickers = cleaned
        from goldsilver.data.signal_strategies import (
            DEFAULT_MARKER_MOMENTUM,
            DEFAULT_MARKER_RECOIL,
            STRATEGY_NAMES,
        )

        merged = _default_visible_signals()
        for name, on in self.visible_signals.items():
            if name in merged:
                merged[name] = bool(on)
        self.visible_signals = merged
        if self.marker_momentum_strategy not in STRATEGY_NAMES:
            self.marker_momentum_strategy = DEFAULT_MARKER_MOMENTUM
        if self.marker_recoil_strategy not in STRATEGY_NAMES:
            self.marker_recoil_strategy = DEFAULT_MARKER_RECOIL
        clean_params: dict[str, dict[str, float]] = {}
        for name, kv in self.signal_params.items():
            if name not in STRATEGY_NAMES or not isinstance(kv, dict):
                continue
            clean_params[name] = {
                str(k): float(v)
                for k, v in kv.items()
                if isinstance(v, (int, float))
            }
        self.signal_params = clean_params

    @classmethod
    def load(cls) -> "AppSettings":
        path = settings_path()
        if not path.exists():
            return cls()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()
        if not isinstance(raw, dict):
            return cls()
        allowed = {f.name for f in fields(cls)}
        clean = {k: v for k, v in raw.items() if k in allowed}
        try:
            return cls(**{**asdict(cls()), **clean})
        except TypeError:
            return cls()

    def save(self) -> None:
        path = settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(self), indent=2), encoding="utf-8"
        )

    def gold_rgb(self) -> tuple[int, int, int]:
        return GOLD_PRESETS.get(self.gold_color_name, GOLD_PRESETS[DEFAULT_GOLD])

    def silver_rgb(self) -> tuple[int, int, int]:
        return SILVER_PRESETS.get(
            self.silver_color_name, SILVER_PRESETS[DEFAULT_SILVER]
        )


def settings_path() -> Path:
    if os.name == "nt":
        base = Path(
            os.environ.get("APPDATA")
            or Path.home() / "AppData" / "Roaming"
        )
    else:
        base = Path(
            os.environ.get("XDG_CONFIG_HOME")
            or Path.home() / ".config"
        )
    return base / "goldsilver" / "settings.json"
