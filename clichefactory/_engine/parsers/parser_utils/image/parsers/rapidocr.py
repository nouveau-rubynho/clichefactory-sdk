"""
RapidOCR image parser: OCR images using RapidOCR.
Returns VlmNormalizedDoc(markdown). Thin wrapper around image pipeline.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from clichefactory._engine.adapters.vlm_adapter import VlmNormalizedDoc
from clichefactory._engine.models.normalized_doc import NormalizedDoc
from clichefactory._engine.parsers.media_parser import MediaParser
from clichefactory._engine.parsers.parser_utils.image import ImagePipelineOptions, run_ocr

if TYPE_CHECKING:
    from clichefactory._engine.config.base_config import AioConfig


class RapidOcrImageParser(MediaParser):
    """
    MediaParser for images using RapidOCR.
    Uses image_parser_lang from config (RapidOCR uses global/multilingual by default).
    """

    def __init__(
        self,
        cacher=None,
        cache_key_fn=None,
        media_parser_registry=None,
        *,
        lang: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(
            cacher=cacher,
            cache_key_fn=cache_key_fn,
            media_parser_registry=media_parser_registry,
            **kwargs,
        )
        config = getattr(media_parser_registry, "config", None) if media_parser_registry else None
        self._lang = lang or (
            getattr(config, "image_parser_lang", "slv+eng") if config else "slv+eng"
        )

    def document_parse(self, content: bytes, filename: str) -> NormalizedDoc:
        options = ImagePipelineOptions(engine="rapidocr", lang=self._lang)
        md = run_ocr(content, filename, options)
        return VlmNormalizedDoc([(1, None, md or "[No text extracted from image]")])
