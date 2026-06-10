"""Shared httpx client factory so every feed gets uniform timeout and pooling policy."""

from __future__ import annotations

import httpx

DEFAULT_TIMEOUT_S = 10.0


def make_client(
    *,
    headers: dict[str, str] | None = None,
    timeout: float = DEFAULT_TIMEOUT_S,
    follow_redirects: bool = False,
) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers=headers,
        timeout=timeout,
        follow_redirects=follow_redirects,
    )
