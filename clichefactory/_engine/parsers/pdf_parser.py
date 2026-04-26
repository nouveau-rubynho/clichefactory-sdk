"""
PdfRouterParser: single entry point for PDF parsing.
Classifies PDF as structured or image, routes to appropriate strategy.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from clichefactory._engine.models.normalized_doc import NormalizedDoc
from clichefactory._engine.parsers.parser_utils.pdf import classify_pdf
from clichefactory._engine.parsers.parser_utils.pdf.strategies.pymupdf_structured import (
    PymupdfStructuredStrategy,
)
from clichefactory._engine.parsers.media_parser import MediaParser

if TYPE_CHECKING:
    from clichefactory._engine.config.base_config import AioConfig

logger = logging.getLogger(__name__)


class PdfRouterParser(MediaParser):
    """
    Single entry point for .pdf parsing.
    - Classifies PDF as structured (native text) or image (scanned).
    - Structured -> PyMuPDF strategy (fast, layout-preserving).
    - Image -> selected image strategy (docling, docling_vlm, ocr_llm, yolo_per_partes).
    - Optional: if structured fails and pdf_structured_fallback_to_image, retry with image.
    """

    def __init__(
        self,
        cacher=None,
        cache_key_fn=None,
        media_parser_registry=None,
        *,
        config: "AioConfig | None" = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            cacher=cacher,
            cache_key_fn=cache_key_fn,
            media_parser_registry=media_parser_registry,
            **kwargs,
        )
        self._config = config or getattr(media_parser_registry, "config", None)
        self._structured_strategy = PymupdfStructuredStrategy()
        self._image_parser: MediaParser | None = None

    def _get_image_parser(self) -> MediaParser:
        if self._image_parser is not None:
            return self._image_parser

        from clichefactory._engine.parsers.fallback_media_parser import FallbackMediaParser
        from clichefactory._engine.parsers.parser_utils.pdf.strategies.ocr_llm import OcrLlmPdfParser
        from clichefactory._engine.parsers.parser_utils.pdf.strategies import (
            DoclingBaselineStrategy,
            DoclingVlmStrategy,
        )

        pdf_parser_map = {
            "docling": DoclingBaselineStrategy,
            "docling_vlm": DoclingVlmStrategy,
            "ocr_llm": OcrLlmPdfParser,
        }

        try:
            from clichefactory_internal.parsers.strategies.yolo_per_partes import YoloPerPartesStrategy

            pdf_parser_map["yolo_per_partes"] = YoloPerPartesStrategy
        except ImportError:
            # YOLO strategy is not available in public-only installs.
            pass
        selected_cls = pdf_parser_map.get(
            getattr(self._config, "pdf_image_parser", "docling"),
            DoclingBaselineStrategy,
        )

        if (
            selected_cls is not OcrLlmPdfParser
            and getattr(self._config, "pdf_fallback_to_ocr_llm", True)
        ):

            class ImageWithOcrFallback(FallbackMediaParser):
                def __init__(self, **kw: Any) -> None:
                    super().__init__(
                        primary_cls=selected_cls,
                        fallback_cls=OcrLlmPdfParser,
                        **kw,
                    )

            self._image_parser = ImageWithOcrFallback(
                cacher=self._cacher,
                cache_key_fn=self._cache_key_fn,
                media_parser_registry=self._media_parser_registry,
            )
        else:
            self._image_parser = selected_cls(
                cacher=self._cacher,
                cache_key_fn=self._cache_key_fn,
                media_parser_registry=self._media_parser_registry,
            )
        return self._image_parser

    def document_parse(self, content: bytes, filename: str) -> NormalizedDoc:
        kind = classify_pdf(content)

        if kind == "structured":
            try:
                doc = self._structured_strategy.parse(content, filename)
                md = doc.get_markdown().strip()
                if md and "[No text on this page]" not in md:
                    return doc
                # Empty or degenerate output
                structured_failed = True
            except Exception as e:
                logger.warning(
                    "PyMuPDF structured strategy failed for %s: %s",
                    filename,
                    e,
                )
                structured_failed = True

            if getattr(self._config, "pdf_structured_fallback_to_image", False):
                logger.info(
                    "Falling back to image strategy for %s (pdf_structured_fallback_to_image)",
                    filename,
                )
                return self._get_image_parser().document_parse(content, filename)
            if structured_failed:
                raise

        return self._get_image_parser().document_parse(content, filename)
