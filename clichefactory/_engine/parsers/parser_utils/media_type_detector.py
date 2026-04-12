from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import mimetypes
import re


@dataclass(frozen=True)
class DetectedMedia:
    """
    Result of media type detection.

    - extension: a normalized extension ('.pdf', '.eml', '.docx', ...)
    - mime: best-effort mime type (may be None)
    - confidence: 0.0..1.0 rough confidence score
    - reason: short explanation (useful for logging/debugging)
    """
    extension: str
    mime: Optional[str]
    confidence: float
    reason: str


class MediaTypeDetector:
    """
    Detect media type from (filename, content) with simple heuristics.

    Design goals:
    - deterministic and fast
    - no heavy dependencies
    - good enough to route to your MediaParserRegistry
    """

    # Map extensions to canonical mimes (only for types you care about).
    _EXT_TO_MIME: dict[str, str] = {
        ".pdf": "application/pdf",
        ".eml": "message/rfc822",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".doc": "application/msword",
        ".odt": "application/vnd.oasis.opendocument.text",
        ".csv": "text/csv",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".html": "text/html",
        ".htm": "text/html",
    }

    # Magic numbers / signatures
    _PDF_MAGIC = b"%PDF-"
    _PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
    _JPG_MAGIC = b"\xff\xd8\xff"
    _GIF_MAGIC = b"GIF87a"  # or GIF89a
    _GIF_MAGIC2 = b"GIF89a"
    _RIFF_MAGIC = b"RIFF"   # WEBP is RIFF....WEBP
    _ZIP_MAGIC = b"PK\x03\x04"  # docx/odt are zip containers

    # Some RFC5322-ish headers seen in .eml
    _EML_HEADER_RE = re.compile(
        r"(?im)^(from|to|cc|bcc|subject|date|message-id|mime-version):\s+.+$"
    )

    def __init__(self, prefer_extension: bool = True, sniff_bytes: int = 4096) -> None:
        self.prefer_extension = prefer_extension
        self.sniff_bytes = sniff_bytes

    def detect(self, content: bytes, filename: str = "") -> DetectedMedia:
        """
        Return DetectedMedia for routing.

        Strategy:
        1) filename extension (if present and prefer_extension=True)
        2) byte sniffing (PDF, images, ZIP-based office, EML-like text)
        3) mimetypes fallback
        """
        ext = self._norm_ext(filename)

        head = content[: self.sniff_bytes] if content else b""

        # 1) Extension-first path (highly practical in real systems)
        if self.prefer_extension and ext:
            mime = self._EXT_TO_MIME.get(ext) or mimetypes.guess_type(filename)[0]
            if mime:
                return DetectedMedia(
                    extension=ext,
                    mime=mime,
                    confidence=0.95,
                    reason=f"filename extension {ext}",
                )
            # If extension is present but unknown, still return it as a routing key
            return DetectedMedia(
                extension=ext,
                mime=None,
                confidence=0.6,
                reason=f"unknown extension {ext}",
            )

        # 2) Sniff bytes
        sniffed = self._sniff_bytes(head)
        if sniffed is not None:
            return sniffed

        # 3) Fallback: mimetypes from filename if any
        if filename:
            mime = mimetypes.guess_type(filename)[0]
            if mime:
                # Try to turn mime into an extension; else use filename ext or ".bin"
                ext2 = ext or (mimetypes.guess_extension(mime) or ".bin")
                return DetectedMedia(
                    extension=ext2,
                    mime=mime,
                    confidence=0.6,
                    reason="mimetypes fallback",
                )

        # 4) Final fallback
        return DetectedMedia(
            extension=ext or ".bin",
            mime="application/octet-stream",
            confidence=0.1,
            reason="default fallback",
        )

    def _sniff_bytes(self, head: bytes) -> Optional[DetectedMedia]:
        if not head:
            return None

        # PDF
        if head.startswith(self._PDF_MAGIC):
            return DetectedMedia(".pdf", "application/pdf", 0.95, "pdf magic header")

        # PNG
        if head.startswith(self._PNG_MAGIC):
            return DetectedMedia(".png", "image/png", 0.95, "png magic header")

        # JPEG
        if head.startswith(self._JPG_MAGIC):
            return DetectedMedia(".jpg", "image/jpeg", 0.95, "jpeg magic header")

        # GIF
        if head.startswith(self._GIF_MAGIC) or head.startswith(self._GIF_MAGIC2):
            return DetectedMedia(".gif", "image/gif", 0.95, "gif magic header")

        # WEBP (RIFF....WEBP)
        if head.startswith(self._RIFF_MAGIC) and b"WEBP" in head[8:16]:
            return DetectedMedia(".webp", "image/webp", 0.9, "webp riff header")

        # ZIP container: could be docx/odt/xlsx/pptx, etc.
        # If you want to be fancy, you can inspect central directory names.
        if head.startswith(self._ZIP_MAGIC):
            # If filename is absent, choose a generic zip-based office default.
            # Most commonly for your system: docx/odt.
            return DetectedMedia(".docx", self._EXT_TO_MIME[".docx"], 0.55, "zip container (likely ooxml)")

        # EML heuristic: looks like text with RFC 5322-ish headers near the top
        if self._looks_like_eml(head):
            return DetectedMedia(".eml", "message/rfc822", 0.8, "rfc5322 header heuristic")

        # Text-ish fallback
        if self._looks_like_text(head):
            return DetectedMedia(".txt", "text/plain", 0.3, "text heuristic")

        return None

    def _looks_like_eml(self, head: bytes) -> bool:
        try:
            s = head.decode("utf-8", errors="ignore")
        except Exception:
            return False

        # Typical emails have headers, blank line, then body
        # We don’t require the blank line (some truncated samples won’t have it)
        header_hits = len(self._EML_HEADER_RE.findall(s))
        return header_hits >= 2  # cheap but effective in practice

    def _looks_like_text(self, head: bytes) -> bool:
        # Very rough heuristic: if it decodes cleanly and has few NUL bytes
        if b"\x00" in head:
            return False
        try:
            head.decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False

    def _norm_ext(self, filename: str) -> str:
        if not filename:
            return ""
        ext = Path(filename).suffix.lower()
        return ext if ext.startswith(".") else (f".{ext}" if ext else "")
