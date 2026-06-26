"""Per-app config paths: %APPDATA%/<app> on Windows, $XDG_CONFIG_HOME/<app> elsewhere."""

from __future__ import annotations

import os
import re
from pathlib import Path

_APP_NAME_RE = re.compile(r"^[a-z0-9_-]+$")


def _os_config_root() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")


def config_base(app_name: str) -> Path:
    if not app_name or not _APP_NAME_RE.match(app_name):
        raise ValueError(f"invalid app_name: {app_name!r}")
    return _os_config_root() / app_name


def settings_path(app_name: str) -> Path:
    return config_base(app_name) / "settings.json"


def trades_path(app_name: str) -> Path:
    return config_base(app_name) / "trades.json"


def reports_dir(app_name: str) -> Path:
    return config_base(app_name) / "reports"
