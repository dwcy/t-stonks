"""Filesystem helpers: crash-safe text writes via tmp file + atomic rename."""

from __future__ import annotations

import os
from pathlib import Path


def atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
