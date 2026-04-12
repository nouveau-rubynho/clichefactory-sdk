"""
Image pipeline options for OCR engines.

Language codes use Tesseract format everywhere (e.g. "eng", "slv+eng").
The SDK converts internally per engine via ``lang_mapping``.

Engine-specific behaviour:
- pytesseract: passes "slv+eng" directly (native format)
- rapidocr:    maps to a script family via LangRec (e.g. "latin", "en")
- easyocr:     maps to ISO 639-1 list (e.g. ["sl", "en"])
- docling:     uses Docling image conversion (no lang param)
- ocr_llm:     no language param (VLM-based)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from clichefactory._engine.parsers.parser_utils.lang_mapping import (
    to_easyocr_list,
    to_rapidocr_script,
    to_tesseract_string,
)


@dataclass(frozen=True)
class ImagePipelineOptions:
    """Options for image OCR pipeline."""

    engine: Literal["pytesseract", "rapidocr", "easyocr", "docling", "ocr_llm"] = "pytesseract"
    lang: str = "eng"

    def get_tesseract_lang(self) -> str:
        """Tesseract format: "eng" or "slv+eng"."""
        return to_tesseract_string(self.lang)

    def get_easyocr_lang(self) -> list[str]:
        """EasyOCR format: ["en"] or ["sl", "en"]."""
        return to_easyocr_list(self.lang)

    def get_rapidocr_lang(self) -> str:
        """RapidOCR LangRec script value: "en", "latin", "cyrillic", etc."""
        return to_rapidocr_script(self.lang)
