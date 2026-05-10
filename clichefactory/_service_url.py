"""Resolve the ClicheFactory service (aio-server) HTTP base URL."""

from __future__ import annotations

import os

# Default points at the public ClicheFactory API. Local development sets
# CLICHEFACTORY_API_URL (e.g. http://localhost:4000 or http://aio-server:8000
# inside Docker networks) to override.
_DEFAULT = "https://api.clichefactory.com"
_ENV = "CLICHEFACTORY_API_URL"


def resolve_service_base_url(explicit: str | None) -> str:
    """Return base URL for aio-server HTTP calls (no trailing slash).

    *explicit* (e.g. ``factory(base_url=...)``) wins when set.
    Otherwise ``CLICHEFACTORY_API_URL`` is used when set in the environment.
    Otherwise *DEFAULT* (local dev).
    """
    if explicit:
        return explicit.rstrip("/")
    return os.environ.get(_ENV, _DEFAULT).rstrip("/")
