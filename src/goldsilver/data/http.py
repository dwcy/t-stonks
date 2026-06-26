"""Facade: re-exports the shared httpx client factory from marketcore."""

from __future__ import annotations

from marketcore.http import DEFAULT_TIMEOUT_S, make_client

__all__ = ["DEFAULT_TIMEOUT_S", "make_client"]
