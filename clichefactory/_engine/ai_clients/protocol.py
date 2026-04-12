"""AIClient protocol: unified interface for OCR and extraction across providers."""
from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class AIClient(Protocol):
    """Unified LLM client for OCR, extraction, and optional end-to-end extraction."""

    def ocr(self, content: bytes, mime: str, prompt: str) -> str:
        """OCR a single document (PDF or image). Returns markdown."""
        ...

    def ocr_pages(
        self, content: bytes, page_numbers: list[int], prompt: str
    ) -> dict[int, str]:
        """OCR specific pages of a PDF. Returns {page_no: markdown}."""
        ...

    def ocr_images(
        self, prompt: str, images: list[bytes], mime: str = "image/png"
    ) -> str:
        """OCR multiple images in one request. Returns combined markdown."""
        ...

    def ocr_batch(
        self, items: list[tuple[bytes, str]], prompt: str
    ) -> list[str]:
        """OCR a batch of (content_bytes, mime) items. Returns list of markdown strings."""
        ...

    def extract(
        self,
        text: str,
        schema: type[T],
        prompt: str | None = None,
        *,
        raise_on_validation_error: bool = True,
    ) -> T:
        """Direct extraction: text + schema -> Pydantic instance. No DSPy."""
        ...

    def extract_json(
        self,
        text: str,
        prompt: str,
    ) -> dict:
        """Schema-less JSON extraction: text + prompt -> plain dict.

        Unlike ``extract``, this never sends a ``response_schema`` to the
        provider.  The LLM is asked to return ``application/json`` and the
        response is parsed into a Python dict.  Use this for freeform /
        suggest-model flows where no Pydantic model is available.
        """
        ...

    def extract_from_bytes(
        self,
        content: bytes,
        mime: str,
        schema: type[T],
        prompt: str | None = None,
        *,
        raise_on_validation_error: bool = True,
    ) -> T:
        """End-to-end extraction: bytes + schema -> Pydantic instance. OCR + extract in one call when supported."""
        ...
