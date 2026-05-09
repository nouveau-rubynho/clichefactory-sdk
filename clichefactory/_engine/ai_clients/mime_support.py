"""MIME-type support helpers for direct ``extract_from_bytes`` calls.

The major hosted multimodal LLMs (Gemini, OpenAI, Anthropic) accept a
limited set of MIME types as raw bytes in their vision/document APIs.
Anything outside that set (EML, DOCX, XLSX, ODT, …) must be parsed to
markdown locally before the LLM can extract from it.

Each :class:`~clichefactory._engine.ai_clients.protocol.AIClient`
implementation declares its own supported set via ``supports_bytes``.
The free function :func:`client_supports_bytes` wraps that lookup and
falls back to a conservative default for clients that do not implement
it (e.g. user-supplied ``AIClient`` subclasses written before this API
existed).
"""
from __future__ import annotations

from typing import Final


DEFAULT_DIRECT_BYTES_MIMES: Final[frozenset[str]] = frozenset(
    {
        "application/pdf",
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/gif",
        "image/webp",
    }
)
"""MIME types accepted by mainstream multimodal LLMs as raw bytes.

This is the conservative intersection of Gemini, OpenAI, and Anthropic
vision/document APIs. Vendors may extend this list (e.g. with HEIC, BMP,
TIFF, audio, video); each :class:`AIClient` declares its own list via
``supports_bytes``.
"""


def _normalize_mime(mime: str | None) -> str:
    if not mime:
        return ""
    return mime.lower().split(";", 1)[0].strip()


def is_default_direct_bytes_mime(mime: str | None) -> bool:
    """Return ``True`` when *mime* is in the conservative default set.

    The default set is the intersection of mainstream multimodal LLM
    capabilities. Use this as a fallback for clients that do not
    implement ``supports_bytes``.
    """
    return _normalize_mime(mime) in DEFAULT_DIRECT_BYTES_MIMES


def client_supports_bytes(client: object, mime: str | None) -> bool:
    """Return ``True`` when *client* accepts *mime* for ``extract_from_bytes``.

    Uses the client's ``supports_bytes`` method when available; otherwise
    falls back to :func:`is_default_direct_bytes_mime`. The fallback keeps
    BYO ``AIClient`` implementations working without code changes — they
    will route the same set of MIMEs through bytes that Gemini / OpenAI /
    Anthropic accept.
    """
    fn = getattr(client, "supports_bytes", None)
    if callable(fn):
        try:
            return bool(fn(mime))
        except Exception:
            return is_default_direct_bytes_mime(mime)
    return is_default_direct_bytes_mime(mime)
