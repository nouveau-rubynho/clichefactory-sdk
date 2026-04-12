"""
ImageRouterParser: single entry point for image parsing.
Routes to pytesseract/rapidocr/docling/ocr_llm based on config.
Optionally wraps in FallbackMediaParser (primary -> ocr_llm fallback).
"""
from __future__ import annotations

from typing import Any

from clichefactory._engine.models.normalized_doc import NormalizedDoc
from clichefactory._engine.parsers.fallback_media_parser import FallbackMediaParser
from clichefactory._engine.parsers.media_parser import MediaParser
from clichefactory._engine.parsers.parser_utils.image.parsers import (
    DoclingImageParser,
    OcrLlmImageParser,
    PytesseractImageParser,
    RapidOcrImageParser,
)


class ImageRouterParser(MediaParser):
    """
    Single entry point for image parsing (.png, .jpg, etc.).
    Reads image_parser and image_parser_fallback from config.
    """

    _IMAGE_PARSER_MAP = {
        "pytesseract": PytesseractImageParser,
        "rapidocr": RapidOcrImageParser,
        "docling": DoclingImageParser,
        "ocr_llm": OcrLlmImageParser,
    }

    def __init__(
        self,
        cacher=None,
        cache_key_fn=None,
        media_parser_registry=None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            cacher=cacher,
            cache_key_fn=cache_key_fn,
            media_parser_registry=media_parser_registry,
            **kwargs,
        )
        self._inner_parser: MediaParser | None = None

    def _get_inner_parser(self) -> MediaParser:
        if self._inner_parser is not None:
            return self._inner_parser

        config = getattr(self._media_parser_registry, "config", None)
        primary_name = getattr(config, "image_parser", "pytesseract") if config else "pytesseract"
        use_fallback = getattr(config, "image_parser_fallback", True) if config else True

        primary_cls = self._IMAGE_PARSER_MAP.get(primary_name, PytesseractImageParser)

        if use_fallback:
            self._inner_parser = FallbackMediaParser(
                primary_cls=primary_cls,
                fallback_cls=OcrLlmImageParser,
                cacher=self._cacher,
                cache_key_fn=self._cache_key_fn,
                media_parser_registry=self._media_parser_registry,
            )
        else:
            self._inner_parser = primary_cls(
                cacher=self._cacher,
                cache_key_fn=self._cache_key_fn,
                media_parser_registry=self._media_parser_registry,
            )
        return self._inner_parser

    def document_parse(self, content: bytes, filename: str) -> NormalizedDoc:
        return self._get_inner_parser().document_parse(content, filename)
