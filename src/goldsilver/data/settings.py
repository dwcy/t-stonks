from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Literal

from goldsilver.fsutil import atomic_write_text
from goldsilver.reports.constants import (
    CONCURRENCY_BOUNDS,
    DEFAULT_ALLOWED_TOOLS,
    DEFAULT_INTERVAL_MINUTES,
    DEFAULT_MAX_CONCURRENCY,
    DEFAULT_OUT_DIR,
    DEFAULT_TIMEOUT_SECONDS,
    INTERVAL_BOUNDS,
    KNOWN_TOOLS,
    TIMEOUT_BOUNDS,
)


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

ALLOWED_MINI_TILES: tuple[str, ...] = (
    "USDSEK",
    "CADSEK",
    "EURSEK",
    "BTC",
    "BRENT",
    "COPPER",
    "RATIO",
    "DXY",
    "REALYIELD",
)


def _default_mini_tiles() -> list[str]:
    return ["USDSEK", "CADSEK", "EURSEK", "COPPER", "BTC", "BRENT", "RATIO"]


SellMode = Literal["all", "percent"]
TriggerMode = Literal["both", "either"]

DEFAULT_INITIAL_DEPOSIT = 100_000.0


@dataclass(slots=True)
class SimulatorSettings:
    enabled: bool = False
    initial_deposit: float = DEFAULT_INITIAL_DEPOSIT
    buy_pct: float = 0.10
    sell_mode: SellMode = "all"
    sell_pct: float = 0.50
    trigger_mode: TriggerMode = "either"

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            self.enabled = bool(self.enabled)
        try:
            self.initial_deposit = float(self.initial_deposit)
        except (TypeError, ValueError):
            self.initial_deposit = DEFAULT_INITIAL_DEPOSIT
        if self.initial_deposit <= 0.0:
            self.initial_deposit = DEFAULT_INITIAL_DEPOSIT
        try:
            self.buy_pct = float(self.buy_pct)
        except (TypeError, ValueError):
            self.buy_pct = 0.10
        if not (0.0 < self.buy_pct <= 1.0):
            self.buy_pct = 0.10
        if self.sell_mode not in ("all", "percent"):
            self.sell_mode = "all"
        try:
            self.sell_pct = float(self.sell_pct)
        except (TypeError, ValueError):
            self.sell_pct = 0.50
        if not (0.0 < self.sell_pct <= 1.0):
            self.sell_pct = 0.50
        if self.trigger_mode not in ("both", "either"):
            self.trigger_mode = "either"


def _default_report_tickers() -> list[str]:
    return []


def _default_allowed_tools() -> list[str]:
    return list(DEFAULT_ALLOWED_TOOLS)


def _clamp(value: int, bounds: tuple[int, int], fallback: int) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return fallback
    lo, hi = bounds
    if n < lo:
        return lo
    if n > hi:
        return hi
    return n


@dataclass(slots=True)
class ReportSettings:
    enabled: bool = False
    interval_minutes: int = DEFAULT_INTERVAL_MINUTES
    report_tickers: list[str] = field(default_factory=_default_report_tickers)
    report_excluded: list[str] = field(default_factory=list)
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY
    allowed_tools: list[str] = field(default_factory=_default_allowed_tools)
    out_dir: str = DEFAULT_OUT_DIR

    def __post_init__(self) -> None:
        self.enabled = bool(self.enabled)
        self.interval_minutes = _clamp(
            self.interval_minutes, INTERVAL_BOUNDS, DEFAULT_INTERVAL_MINUTES
        )
        self.timeout_seconds = _clamp(
            self.timeout_seconds, TIMEOUT_BOUNDS, DEFAULT_TIMEOUT_SECONDS
        )
        self.max_concurrency = _clamp(
            self.max_concurrency, CONCURRENCY_BOUNDS, DEFAULT_MAX_CONCURRENCY
        )
        if not isinstance(self.report_tickers, list):
            self.report_tickers = _default_report_tickers()
        else:
            cleaned: list[str] = []
            seen: set[str] = set()
            for raw in self.report_tickers:
                if not isinstance(raw, str):
                    continue
                t = raw.strip().upper()
                if not t or t in seen:
                    continue
                seen.add(t)
                cleaned.append(t)
            self.report_tickers = cleaned
        if not isinstance(self.report_excluded, list):
            self.report_excluded = []
        else:
            excluded: list[str] = []
            seen_ex: set[str] = set()
            for raw in self.report_excluded:
                if not isinstance(raw, str):
                    continue
                t = raw.strip().upper()
                if not t or t in seen_ex:
                    continue
                seen_ex.add(t)
                excluded.append(t)
            self.report_excluded = excluded
        if not isinstance(self.allowed_tools, list):
            self.allowed_tools = _default_allowed_tools()
        else:
            tools = [t for t in self.allowed_tools if t in KNOWN_TOOLS]
            self.allowed_tools = tools or _default_allowed_tools()
        if not isinstance(self.out_dir, str) or not self.out_dir.strip():
            self.out_dir = DEFAULT_OUT_DIR


DEFAULT_ACTUALS_GRACE_MINUTES = 5
DEFAULT_ACTUALS_TIMEOUT_SECONDS = 180
DEFAULT_ACTUALS_MAX_CONCURRENCY = 2
ACTUALS_GRACE_BOUNDS: tuple[int, int] = (0, 120)
ACTUALS_TIMEOUT_BOUNDS: tuple[int, int] = (30, 900)
ACTUALS_CONCURRENCY_BOUNDS: tuple[int, int] = (1, 8)


@dataclass(slots=True)
class CalendarSettings:
    actuals_enabled: bool = False
    actuals_grace_minutes: int = DEFAULT_ACTUALS_GRACE_MINUTES
    actuals_timeout_seconds: int = DEFAULT_ACTUALS_TIMEOUT_SECONDS
    actuals_max_concurrency: int = DEFAULT_ACTUALS_MAX_CONCURRENCY

    def __post_init__(self) -> None:
        self.actuals_enabled = bool(self.actuals_enabled)
        self.actuals_grace_minutes = _clamp(
            self.actuals_grace_minutes,
            ACTUALS_GRACE_BOUNDS,
            DEFAULT_ACTUALS_GRACE_MINUTES,
        )
        self.actuals_timeout_seconds = _clamp(
            self.actuals_timeout_seconds,
            ACTUALS_TIMEOUT_BOUNDS,
            DEFAULT_ACTUALS_TIMEOUT_SECONDS,
        )
        self.actuals_max_concurrency = _clamp(
            self.actuals_max_concurrency,
            ACTUALS_CONCURRENCY_BOUNDS,
            DEFAULT_ACTUALS_MAX_CONCURRENCY,
        )


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
    chart_zoom2: ChartZoom = "3h"
    chart_mode: ChartMode = "live"
    show_dual_charts: bool = False
    chart_kind2: ChartKind = "candle"
    show_sma: bool = False
    show_vwap: bool = False
    show_day_refs: bool = False
    signal_mode: SignalMode = "MOMENTUM"
    show_news_markets: bool = True
    show_news_trump: bool = True
    show_congress_trades: bool = False
    show_insider_trades: bool = False
    show_stocktwits: bool = False
    show_stock_row: bool = True
    gold_color_name: str = DEFAULT_GOLD
    silver_color_name: str = DEFAULT_SILVER
    metals_columns: int = 2
    stock_tickers: list[str] = field(default_factory=_default_stock_tickers)
    mini_tiles: list[str] = field(default_factory=_default_mini_tiles)
    visible_signals: dict[str, bool] = field(default_factory=_default_visible_signals)
    signal_params: dict[str, dict[str, float]] = field(
        default_factory=_default_signal_params
    )
    marker_momentum_strategy: str = ""
    marker_recoil_strategy: str = ""
    simulator: SimulatorSettings = field(default_factory=SimulatorSettings)
    report: ReportSettings = field(default_factory=ReportSettings)
    calendar: CalendarSettings = field(default_factory=CalendarSettings)

    def __post_init__(self) -> None:
        if self.metals_columns not in METALS_COLUMNS_CHOICES:
            self.metals_columns = 2
        if self.chart_zoom not in CHART_ZOOM_CHOICES:
            self.chart_zoom = "24h"
        if self.chart_zoom2 not in CHART_ZOOM_CHOICES:
            self.chart_zoom2 = "3h"
        if self.chart_mode not in CHART_MODE_CHOICES:
            self.chart_mode = "live"
        if self.chart_kind not in ("line", "candle"):
            self.chart_kind = "line"
        if self.chart_kind2 not in ("line", "candle"):
            self.chart_kind2 = "candle"
        self.show_dual_charts = bool(self.show_dual_charts)
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
        if not isinstance(self.mini_tiles, list):
            self.mini_tiles = _default_mini_tiles()
        else:
            cleaned_tiles: list[str] = []
            seen_tiles: set[str] = set()
            for raw in self.mini_tiles:
                if not isinstance(raw, str):
                    continue
                if raw not in ALLOWED_MINI_TILES or raw in seen_tiles:
                    continue
                seen_tiles.add(raw)
                cleaned_tiles.append(raw)
            self.mini_tiles = cleaned_tiles
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
                str(k): float(v) for k, v in kv.items() if isinstance(v, (int, float))
            }
        self.signal_params = clean_params
        if not isinstance(self.simulator, SimulatorSettings):
            if isinstance(self.simulator, dict):
                allowed_sim = {f.name for f in fields(SimulatorSettings)}
                clean_sim = {
                    k: v for k, v in self.simulator.items() if k in allowed_sim
                }
                try:
                    self.simulator = SimulatorSettings(**clean_sim)
                except TypeError:
                    self.simulator = SimulatorSettings()
            else:
                self.simulator = SimulatorSettings()
        if not isinstance(self.report, ReportSettings):
            if isinstance(self.report, dict):
                allowed_report = {f.name for f in fields(ReportSettings)}
                clean_report = {
                    k: v for k, v in self.report.items() if k in allowed_report
                }
                try:
                    self.report = ReportSettings(**clean_report)
                except TypeError:
                    self.report = ReportSettings()
            else:
                self.report = ReportSettings()
        if not isinstance(self.calendar, CalendarSettings):
            if isinstance(self.calendar, dict):
                allowed_cal = {f.name for f in fields(CalendarSettings)}
                clean_cal = {k: v for k, v in self.calendar.items() if k in allowed_cal}
                try:
                    self.calendar = CalendarSettings(**clean_cal)
                except TypeError:
                    self.calendar = CalendarSettings()
            else:
                self.calendar = CalendarSettings()

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
        atomic_write_text(path, json.dumps(asdict(self), indent=2))

    def gold_rgb(self) -> tuple[int, int, int]:
        return GOLD_PRESETS.get(self.gold_color_name, GOLD_PRESETS[DEFAULT_GOLD])

    def silver_rgb(self) -> tuple[int, int, int]:
        return SILVER_PRESETS.get(
            self.silver_color_name, SILVER_PRESETS[DEFAULT_SILVER]
        )


def _config_base() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")


def settings_path() -> Path:
    return _config_base() / "goldsilver" / "settings.json"


def trades_path() -> Path:
    return _config_base() / "goldsilver" / "trades.json"
