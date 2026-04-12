"""
Docling VLM PDF strategy: per-page refinement with OCR LLM.
"""
from __future__ import annotations

import io
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO

from clichefactory._engine.adapters.vlm_adapter import PageMarkdownItem, VlmNormalizedDoc
from clichefactory._engine.ai_clients import AIClient, create_ai_client
from clichefactory._engine.models.normalized_doc import NormalizedDoc
from clichefactory._engine.parsers.media_parser import MediaParser
from clichefactory._engine.parsers.parser_utils.pdf.docling_helpers import (
    build_per_page_markdown,
    page_to_pil,
)
from clichefactory._engine.parsers.parser_utils.pdf.docling_pipeline_options import get_pdf_pipeline_options
from clichefactory._engine.parsers.parser_utils.pdf_repair import repair_pdf_bytes
from docling.datamodel.base_models import InputFormat
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.io import DocumentStream

from clichefactory._engine.parsers.parser_utils.prompts import FULL_PAGE_VLM_PROMPT
from clichefactory.errors import ConfigurationError, ErrorInfo

logger = logging.getLogger(__name__)


class DoclingVlmStrategy(MediaParser):
    """
    Deep Clean: per-page refinement.
    DocLayNet + OCR for full doc; each page sent to OCR LLM for refinement.
    """

    def __init__(
        self,
        cacher=None,
        cache_key_fn=None,
        media_parser_registry=None,
        *,
        ocr_client: AIClient | None = None,
        max_workers: int = 4,
        ocr_engine: str | None = None,
        ocr_lang: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(
            cacher=cacher,
            cache_key_fn=cache_key_fn,
            media_parser_registry=media_parser_registry,
            **kwargs,
        )
        config = getattr(media_parser_registry, "config", None)
        self._ocr_engine = ocr_engine or (
            getattr(config, "pdf_ocr_engine", None) or "tesseract"
        )
        self._ocr_lang = ocr_lang or (
            getattr(config, "pdf_ocr_lang", None) or "slv+eng"
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
                        message="Docling VLM parsing requires AioConfig on the media parser registry.",
                        hint=(
                            "Use the SDK in local mode with factory(model=Endpoint(...)) "
                            "or set registry.config for standalone engine use."
                        ),
                    )
                )
        self._max_workers = max(1, min(10, max_workers))

    def document_parse(self, content: bytes, filename: str) -> NormalizedDoc:
        pipeline_options = get_pdf_pipeline_options(
            generate_page_images=True,
            ocr_engine=self._ocr_engine,
            ocr_lang=self._ocr_lang,
        )
        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
            }
        )
        try:
            conversion_result = converter.convert(
                DocumentStream(name=filename, stream=BytesIO(content))
            )
        except Exception as e:
            logger.warning(
                "DoclingVlmStrategy conversion failed for %s: %s; attempting PDF repair",
                filename,
                e,
            )
            repaired = repair_pdf_bytes(content)
            if repaired is content:
                raise
            conversion_result = converter.convert(
                DocumentStream(name=filename, stream=BytesIO(repaired))
            )
            content = repaired

        doc = conversion_result.document
        page_numbers = sorted(doc.pages.keys())
        per_page_markdown = build_per_page_markdown(doc)

        page_results: dict[int, tuple[tuple[float, float] | None, str]] = {}

        def refine_page(page_no: int) -> None:
            page = doc.pages[page_no]
            pil_image = page_to_pil(page)
            size_tuple = None
            if hasattr(page, "size") and page.size is not None:
                size_tuple = (float(page.size.width), float(page.size.height))

            if pil_image is None:
                page_results[page_no] = (size_tuple, "")
                return

            page_md = per_page_markdown.get(page_no, "")
            prompt = FULL_PAGE_VLM_PROMPT.format(
                page_markdown=page_md or "(No OCR content for this page)"
            )

            buf = io.BytesIO()
            pil_image.save(buf, format="PNG")
            buf.seek(0)
            text = self._ocr_client.ocr(buf.getvalue(), "image/png", prompt)
            page_results[page_no] = (size_tuple, text)

        workers = min(self._max_workers, len(page_numbers)) if page_numbers else 0
        if workers <= 0:
            page_items: list[PageMarkdownItem] = []
        elif workers == 1:
            for pno in page_numbers:
                refine_page(pno)
            page_items = [
                (pno, page_results[pno][0], page_results[pno][1])
                for pno in page_numbers
            ]
        else:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_to_page = {
                    executor.submit(refine_page, pno): pno for pno in page_numbers
                }
                for future in as_completed(future_to_page):
                    future.result()
            page_items = [
                (pno, page_results[pno][0], page_results[pno][1])
                for pno in page_numbers
            ]

        return VlmNormalizedDoc(page_items)
