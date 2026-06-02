"""Pytest config + shared fixtures."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def isolated_trades_path(monkeypatch: pytest.MonkeyPatch) -> Path:
    import goldsilver.data.trades_service as ts_mod

    tmp = Path(tempfile.mkdtemp()) / "trades.json"
    monkeypatch.setattr(ts_mod, "trades_path", lambda: tmp)
    return tmp
