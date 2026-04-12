from clichefactory._engine.models.normalized_doc import NormalizedDoc
from clichefactory._engine.parsers.media_parser import MediaParser
from clichefactory._engine.parsers.parser_utils.office_converter import convert_office_bytes_to_pdf_bytes
from clichefactory._engine.parsers.parser_utils.pdf.strategies import DoclingBaselineStrategy
from clichefactory._engine.parsers.parser_utils.media_type_detector import MediaTypeDetector



class DocParser(MediaParser):
    def __init__(self, cacher = None, media_parser_registry=None, **kwargs) -> None:
        super().__init__(cacher=cacher, media_parser_registry=media_parser_registry, **kwargs)
        self.type_detector = MediaTypeDetector()
        self._media_parser_registry = media_parser_registry
        if media_parser_registry is None:
            self._pdf_parser = DoclingBaselineStrategy(cacher=cacher)
        else:
            self._pdf_parser = None

    def convert(self, content: bytes, filename: str) -> bytes:
        media_type = self.type_detector.detect(content, filename)
        return convert_office_bytes_to_pdf_bytes(content, filename, str(media_type.mime))

    def document_parse(self, content: bytes, filename: str) -> NormalizedDoc:
        pdf_bytes = self.convert(content, filename)
        if self._media_parser_registry is not None:
            pdf_parser = self._media_parser_registry.create_parser(".pdf", cacher=self._cacher)
            return pdf_parser.parse(pdf_bytes, filename)
        return self._pdf_parser.parse(pdf_bytes, filename)
