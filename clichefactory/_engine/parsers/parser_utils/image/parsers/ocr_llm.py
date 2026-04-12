"""
OCR LLM image parser: OCR images via the configured OCR LLM client.
Returns VlmNormalizedDoc(markdown). Thin wrapper around image pipeline.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from clichefactory._engine.adapters.vlm_adapter import VlmNormalizedDoc
from clichefactory._engine.ai_clients import AIClient, create_ai_client
from clichefactory._engine.models.normalized_doc import NormalizedDoc
from clichefactory._engine.parsers.media_parser import MediaParser
from clichefactory._engine.parsers.parser_utils.image import ImagePipelineOptions, run_ocr
from clichefactory.errors import ConfigurationError, ErrorInfo

if TYPE_CHECKING:
    from clichefactory._engine.config.base_config import AioConfig


class OcrLlmImageParser(MediaParser):
    """
    MediaParser for images using OcrLlmClient (VLM OCR).
    """

    def __init__(
        self,
        cacher=None,
        cache_key_fn=None,
        media_parser_registry=None,
        *,
        ocr_client: AIClient | None = None,
        **kwargs,
    ) -> None:
        super().__init__(
            cacher=cacher,
            cache_key_fn=cache_key_fn,
            media_parser_registry=media_parser_registry,
            **kwargs,
        )
        if ocr_client is not None:
            self._ocr_client = ocr_client
        else:
            config = getattr(media_parser_registry, "config", None) if media_parser_registry else None
            if config:
                self._ocr_client = create_ai_client(config, purpose="ocr")
            else:
                raise ConfigurationError(
                    ErrorInfo(
                        code="parser.missing_ocr_config",
                        message="OCR LLM image parsing requires AioConfig on the media parser registry.",
                        hint=(
                            "Use the SDK in local mode with factory(model=Endpoint(...)) "
                            "or set registry.config for standalone engine use."
                        ),
                    )
                )

    def document_parse(self, content: bytes, filename: str) -> NormalizedDoc:
        config = getattr(self._media_parser_registry, "config", None)
        usage_tracker = None
        if config:
            usage_tracker = getattr(config, "usage_tracker", None)
            if hasattr(self._ocr_client, "set_cost_tracker"):
                self._ocr_client.set_cost_tracker(usage_tracker)

        options = ImagePipelineOptions(engine="ocr_llm", lang="")
        md = run_ocr(content, filename, options, ocr_client=self._ocr_client)
        doc = VlmNormalizedDoc([(1, None, md.strip() if md else "[No text extracted from image]")])

        if usage_tracker and hasattr(usage_tracker, "summary"):
            doc.cost_summary = usage_tracker.summary()
        if hasattr(self._ocr_client, "set_cost_tracker"):
            self._ocr_client.set_cost_tracker(None)
        return doc
