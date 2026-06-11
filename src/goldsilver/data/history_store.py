"""Disk archive of daily intraday bars for backtesting."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from goldsilver.data.models import GOLD, SILVER, Bar
from goldsilver.data.session import stockholm_date_of
from goldsilver.fsutil import atomic_write_text

HISTORY_DIR = Path(__file__).resolve().parents[3] / "history"
_FOLDER = {GOLD: "gold", SILVER: "silver"}
_INTERVAL = "1m"


def _metal_dir(symbol: str) -> Path:
    return HISTORY_DIR / _FOLDER.get(symbol, symbol.lower())


def day_path(symbol: str, day: date) -> Path:
    return _metal_dir(symbol) / f"{day:%Y%m%d}.json"


def split_by_day(bars: list[Bar]) -> dict[date, list[Bar]]:
    grouped: dict[date, list[Bar]] = {}
    for bar in bars:
        grouped.setdefault(stockholm_date_of(bar.time), []).append(bar)
    return grouped


def save_day(symbol: str, day: date, bars: list[Bar]) -> None:
    path = day_path(symbol, day)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "version": 1,
        "symbol": symbol,
        "day": day.isoformat(),
        "interval": _INTERVAL,
        "bars": [b.model_dump(mode="json") for b in bars],
    }
    atomic_write_text(path, json.dumps(data))


def load_day(symbol: str, day: date) -> list[Bar]:
    path = day_path(symbol, day)
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [Bar(**b) for b in raw["bars"]]
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return []


def available_days(symbol: str) -> list[date]:
    folder = _metal_dir(symbol)
    if not folder.is_dir():
        return []
    days: list[date] = []
    for path in folder.glob("*.json"):
        try:
            stem = path.stem
            days.append(date(int(stem[:4]), int(stem[4:6]), int(stem[6:8])))
        except (ValueError, IndexError):
            continue
    return sorted(days, reverse=True)
