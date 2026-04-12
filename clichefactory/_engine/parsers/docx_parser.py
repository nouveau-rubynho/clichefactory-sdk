# aio/parsers/docx_parser.py
from __future__ import annotations

from io import BytesIO

from clichefactory._engine.adapters.docling_adapter import DoclingNormalizedDoc
from clichefactory._engine.models.normalized_doc import NormalizedDoc
from clichefactory._engine.parsers.media_parser import MediaParser

from docling.datamodel.base_models import InputFormat
from docling.document_converter import DocumentConverter, WordFormatOption
from docling.pipeline.simple_pipeline import SimplePipeline
from docling_core.types.io import DocumentStream


class DocxParser(MediaParser):
    """
    DOCX -> DoclingDocument -> NormalizedDoc
    """

    def __init__(self, cacher=None) -> None:
        super().__init__(cacher=cacher)

        # Minimal, predictable setup
        self._converter = DocumentConverter(
            allowed_formats=[InputFormat.DOCX],
            format_options={
                InputFormat.DOCX: WordFormatOption(
                    pipeline_cls=SimplePipeline,
                    # backend=MsWordDocumentBackend,  # optional: choose backend if needed
                )
            },
        )

    def document_parse(self, content: bytes, filename: str) -> NormalizedDoc:
        coversion_result = self._converter.convert(DocumentStream(name=filename, stream=BytesIO(content)))
        return DoclingNormalizedDoc(coversion_result.document)
