"""Facade: re-exports atomic filesystem helpers from marketcore."""

from __future__ import annotations

from marketcore.fsutil import atomic_write_text

__all__ = ["atomic_write_text"]
