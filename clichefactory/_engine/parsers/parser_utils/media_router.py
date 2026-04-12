import logging

from clichefactory._engine.cache.base_cacher import Cacher
from clichefactory._engine.models.normalized_doc import NormalizedDoc
from clichefactory._engine.parsers.media_parser_registry import MediaParserRegistry
from clichefactory._engine.parsers.parser_utils.media_type_detector import MediaTypeDetector

logger = logging.getLogger(__name__)

class MediaRouter:
    def __init__(
        self,
        registry: MediaParserRegistry,
        cacher: Cacher | None = None,
        detector = MediaTypeDetector()
    ):
        self.registry = registry
        self.cacher = cacher
        self.detector = detector or MediaTypeDetector()

    def parse(self, content: bytes, filename: str) -> NormalizedDoc | None:
        media_type = self.detector.detect(content, filename)
        parser_cls = self.registry.get(media_type.extension)

        if parser_cls is None:
            logger.warning(f"No parser for file {filename} with MIME-type {media_type.mime} and extension {media_type.extension}.")
            return

        parser = self.registry.create_parser(media_type.extension, cacher=self.cacher)
        return parser.parse(content=content, filename=filename)
