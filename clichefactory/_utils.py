from __future__ import annotations

import asyncio
import re
from typing import Any, TypeVar

T = TypeVar("T")


def run_sync(coro: Any) -> Any:
    """
    Run an async coroutine from sync context.

    Assumes it is called when no event loop is running (typical CLI/script usage).
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None:
        raise RuntimeError(
            "Cannot call sync wrapper while an event loop is running. "
            "Use the *_async API instead."
        )
    return asyncio.run(coro)


# ── numeric coercion ──────────────────────────────────────────────────────────

_EU_DECIMAL_RE = re.compile(r"^[0-9]+,[0-9]+$|^[0-9]{1,3}(?:\.[0-9]{3})*,[0-9]+$")
_ACCOUNTING_NEG_RE = re.compile(r"^\((.+)\)$")

_CURRENCY_SYMBOLS: frozenset[str] = frozenset({"$", "€", "£", "¥"})
_CURRENCY_CODES: frozenset[str] = frozenset({
    "USD", "EUR", "GBP", "JPY", "CHF", "SEK", "NOK", "DKK",
    "PLN", "CZK", "HUF", "RON", "BGN", "CAD", "AUD", "NZD",
    "CNY", "INR", "BRL", "MXN", "ZAR",
})


def _parse_numeric_core(s: str) -> float | None:
    """Parse a plain-ish numeric string; returns None if it cannot be converted.

    Tries European decimal-comma format first (``11.720,00`` → 11720.0), then
    falls back to standard ``float()``.  Plain undecorated strings like ``"22"``
    are also accepted here because callers have already verified context (e.g.
    a percent or currency decorator was present).
    """
    if _EU_DECIMAL_RE.match(s):
        try:
            return float(s.replace(".", "").replace(",", "."))
        except ValueError:
            return None
    try:
        return float(s)
    except ValueError:
        return None


def _strip_currency(s: str) -> tuple[str, bool]:
    """Strip a single leading or trailing currency symbol / ISO code.

    Returns ``(stripped_string, changed)`` where ``changed`` is True when
    something was actually removed.
    """
    if not s:
        return s, False
    # Leading symbol  →  $1.5, €12,50
    if s[0] in _CURRENCY_SYMBOLS:
        return s[1:].strip(), True
    # Trailing symbol  →  12,50€
    if s[-1] in _CURRENCY_SYMBOLS:
        return s[:-1].strip(), True
    up = s.upper()
    # Leading ISO code with mandatory space/nbsp  →  EUR 1.234,56
    if len(s) >= 4 and up[:3] in _CURRENCY_CODES and s[3] in (" ", "\xa0"):
        return s[4:].strip(), True
    # Trailing ISO code with mandatory space/nbsp  →  1.234,56 EUR
    if len(s) >= 4 and up[-3:] in _CURRENCY_CODES and s[-4] in (" ", "\xa0"):
        return s[:-4].strip(), True
    return s, False


def _coerce_scalar(v: Any) -> Any:
    """Convert a single LLM-formatted numeric string to a Python ``float``.

    The following patterns are recognised (in order):

    - **Percent suffix** — ``"22 %"`` / ``"22,5%"`` → ``22.5``
    - **Currency prefix/suffix** — ``"EUR 1.234,56"`` / ``"$12.5"`` → float
    - **Accounting negative** — ``"(250,00)"`` → ``-250.0``
    - **European decimal-comma** — ``"11.720,00"`` → ``11720.0``

    Strings that match no pattern are returned **unchanged** so that Pydantic's
    own coercion or a downstream ``postprocess`` hook can handle them.
    """
    if not isinstance(v, str):
        return v
    s = v.strip()
    if not s:
        return v

    # ── percent suffix ───────────────────────────────────────────────────────
    if s.endswith("%"):
        core = s[:-1].strip()
        val = _parse_numeric_core(core)
        if val is not None:
            return val
        return v

    # ── currency prefix / suffix ─────────────────────────────────────────────
    stripped, changed = _strip_currency(s)
    if changed and stripped:
        val = _parse_numeric_core(stripped)
        if val is not None:
            return val
        # stripped but inner part is not numeric — fall through

    # ── accounting negative: (250,00) → -250.0 ──────────────────────────────
    m = _ACCOUNTING_NEG_RE.match(s)
    if m:
        inner = m.group(1).strip()
        inner_stripped, _ = _strip_currency(inner)
        val = _parse_numeric_core(inner_stripped if inner_stripped else inner)
        if val is not None:
            return -val
        return v

    # ── European decimal-comma (no decorator) ────────────────────────────────
    if _EU_DECIMAL_RE.match(s):
        try:
            return float(s.replace(".", "").replace(",", "."))
        except ValueError:
            return v

    return v


def _coerce_numeric_strings(obj: Any) -> Any:
    """Recursively apply :func:`_coerce_scalar` to every leaf in a nested payload."""
    if isinstance(obj, dict):
        return {k: _coerce_numeric_strings(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_coerce_numeric_strings(x) for x in obj]
    return _coerce_scalar(obj)

