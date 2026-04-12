from __future__ import annotations

import json
import re
from typing import Any


def _escape_raw_newlines_in_json_strings(text: str) -> str:
    """
    Repair a common "almost JSON" failure mode:
    JSON strings cannot contain raw unescaped newlines.
    Some model outputs include actual newline characters inside JSON string literals.
    """

    out: list[str] = []
    in_string = False
    escape = False

    for ch in text:
        if not in_string:
            if ch == '"':
                in_string = True
            out.append(ch)
            continue

        # Inside a JSON string literal.
        if escape:
            out.append(ch)
            escape = False
            continue

        if ch == "\\":
            out.append(ch)
            escape = True
            continue

        if ch == '"':
            in_string = False
            out.append(ch)
            continue

        # Escape raw control characters that would break json.loads.
        if ch == "\n":
            out.append("\\n")
            continue
        if ch == "\r":
            out.append("\\r")
            continue
        if ch == "\t":
            out.append("\\t")
            continue

        out.append(ch)

    return "".join(out)


def _extract_json_object_substring(text: str) -> str | None:
    """
    Best-effort extraction of the outermost JSON object from surrounding text.
    This is intentionally simple and only used as a fallback.
    """
    if not text:
        return None

    s = text.strip()
    # Remove common markdown fences if present.
    s = re.sub(
        r"^```(?:json)?\s*|```$",
        "",
        s,
        flags=re.IGNORECASE | re.MULTILINE,
    ).strip()

    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end >= start:
        return s[start : end + 1]
    return None


def safe_json_loads(
    text: str,
    *,
    error_prefix: str = "Invalid JSON",
    snippet_limit: int = 2000,
) -> dict[str, Any]:
    """
    Parse JSON using a few targeted repairs/fallbacks.

    Raises ValueError with a truncated raw snippet on failure.
    """

    raw = (text or "").strip()
    if raw == "":
        return {}

    last_exc: Exception | None = None

    def _fail(exc: Exception) -> ValueError:
        snippet = raw[:snippet_limit].replace("\n", "\\n")
        return ValueError(
            f"{error_prefix}: {exc}. Raw (truncated): {snippet}"
        )

    # 1) Normal parse.
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
        raise ValueError(f"Expected JSON object, got {type(data).__name__}")
    except Exception as exc:
        last_exc = exc

    # 2) Extract JSON substring (if model added surrounding text/code fences).
    candidate = _extract_json_object_substring(raw)
    if candidate is not None:
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
            raise ValueError(f"Expected JSON object, got {type(data).__name__}")
        except Exception as exc:
            last_exc = exc

        # 3) Repair raw newlines inside JSON strings and try again.
        repaired = _escape_raw_newlines_in_json_strings(candidate)
        try:
            data = json.loads(repaired)
            if isinstance(data, dict):
                return data
            raise ValueError(f"Expected JSON object, got {type(data).__name__}")
        except Exception as exc:
            last_exc = exc

    # 4) Final attempt: repair raw newlines on the full raw text.
    repaired = _escape_raw_newlines_in_json_strings(raw)
    try:
        data = json.loads(repaired)
        if isinstance(data, dict):
            return data
        raise ValueError(f"Expected JSON object, got {type(data).__name__}")
    except Exception as exc:
        last_exc = exc

    # Should not be reached, but keeps mypy/linters happy.
    if last_exc is None:
        last_exc = ValueError("Unknown JSON parsing failure")
    raise _fail(last_exc)

