"""Resolve the ClicheFactory service (aio-server) HTTP base URL."""

from __future__ import annotations

import os

# Short term: default for local development. Override with CLICHEFACTORY_API_URL.
# Medium term: change this default to https://api.clichefactory.com when shipping
# public API broadly; local dev sets CLICHEFACTORY_API_URL once.
_DEFAULT = "http://127.0.0.1:4000"
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
