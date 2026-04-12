"""
Per-page OCR PDF parser using the configured OCR LLM client.
Never sends full document, only per-page(s).
"""
from __future__ import annotations

import fitz

from clichefactory._engine.adapters.vlm_adapter import PageMarkdownItem, VlmNormalizedDoc
from clichefactory._engine.ai_clients import AIClient, create_ai_client, SIMPLE_OCR_PROMPT
from clichefactory._engine.models.normalized_doc import NormalizedDoc
from clichefactory._engine.parsers.media_parser import MediaParser
from clichefactory.errors import ConfigurationError, ErrorInfo


def _get_pdf_page_count(content: bytes) -> int:
    """Return number of pages in the PDF."""
    doc = fitz.open(stream=content, filetype="pdf")
    n = len(doc)
    doc.close()
    return n


class OcrLlmPdfParser(MediaParser):
    """
    MediaParser that uses OcrLlmClient.ocr_pages() for per-page OCR.
    Never sends full document; always processes page-by-page.
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
            config = getattr(media_parser_registry, "config", None)
            if config:
                self._ocr_client = create_ai_client(config, purpose="ocr")
            else:
                raise ConfigurationError(
                    ErrorInfo(
                        code="parser.missing_ocr_config",
                        message="OCR LLM parsing requires AioConfig on the media parser registry.",
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

        page_count = _get_pdf_page_count(content)
        if page_count == 0:
            doc = VlmNormalizedDoc([(1, None, "")])
        else:
            page_numbers = list(range(1, page_count + 1))
            page_markdowns = self._ocr_client.ocr_pages(
                content, page_numbers, SIMPLE_OCR_PROMPT.strip()
            )
            page_items: list[PageMarkdownItem] = [
                (pno, None, f"## Page {pno}\n\n{page_markdowns.get(pno, '') or '[OCR failed for this page]'}")
                for pno in page_numbers
            ]
            doc = VlmNormalizedDoc(page_items)

        if usage_tracker and hasattr(usage_tracker, "summary"):
            doc.cost_summary = usage_tracker.summary()
        if hasattr(self._ocr_client, "set_cost_tracker"):
            self._ocr_client.set_cost_tracker(None)
        return doc

    def parse_pages(
        self, content: bytes, page_numbers: list[int]
    ) -> dict[int, str]:
        """Run OCR on specific pages only. For per-page fallback use."""
        return self._ocr_client.ocr_pages(
            content, page_numbers, SIMPLE_OCR_PROMPT.strip()
        )
