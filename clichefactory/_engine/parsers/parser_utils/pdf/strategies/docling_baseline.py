"""
Docling baseline PDF strategy: DocLayNet + OCR, no VLM.
"""
from __future__ import annotations

from io import BytesIO
import logging

from clichefactory._engine.adapters.docling_adapter import DoclingNormalizedDoc
from clichefactory._engine.models.normalized_doc import NormalizedDoc
from clichefactory._engine.parsers.media_parser import MediaParser
from clichefactory._engine.parsers.parser_utils.pdf.docling_pipeline_options import get_pdf_pipeline_options
from clichefactory._engine.parsers.parser_utils.pdf_repair import repair_pdf_bytes
from docling.datamodel.base_models import InputFormat
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.io import DocumentStream

logger = logging.getLogger(__name__)


class DoclingBaselineStrategy(MediaParser):
    """
    Bread & Butter: low-cost, high-speed baseline.
    Uses DocLayNet + configurable OCR (tesseract/rapidocr/easyocr); no VLM.
    """

    def __init__(
        self,
        cacher=None,
        cache_key_fn=None,
        media_parser_registry=None,
        *,
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

    def document_parse(self, content: bytes, filename: str) -> NormalizedDoc:
        pipeline_options = get_pdf_pipeline_options(
            generate_page_images=False,
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
                "DoclingBaselineStrategy conversion failed for %s: %s; attempting PDF repair",
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
        return DoclingNormalizedDoc(conversion_result.document)
