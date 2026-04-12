# media_parser_registry.py
from __future__ import annotations

from typing import Collection, Dict, Type
from clichefactory._engine.parsers.media_parser import MediaParser


class MediaParserRegistry:
    """
    Registry mapping file extensions to MediaParser subclasses.

    Example:
        registry.register(".pdf", PdfParser)
        registry.register(".eml", EmlParser)
        registry.register_many([".docx", ".doc", ".odt"], OfficeParser)

        parser = registry.create_parser(".pdf", cacher=my_cacher)
    """

    def __init__(self) -> None:
        # Key: lowercase file extension
        # Value: MediaParser subclass
        self._registry: Dict[str, Type[MediaParser]] = {}
        # Optional config (AioConfig/TrainingConfig) for parsers that need AIClient
        self.config: object = None

    # ---------------------------------------------------------
    # Registration
    # ---------------------------------------------------------
    def register(self, extension: str, parser_cls: Type[MediaParser]) -> None:
        """Register a parser class for a given file extension."""
        extension = extension.lower()
        if not extension.startswith("."):
            raise ValueError(f"Expected extension beginning with '.', got: {extension}")
        if not issubclass(parser_cls, MediaParser):
            raise ValueError(f"Parser must be a MediaParser subclass, got: {parser_cls}")
        self._registry[extension] = parser_cls
    
    def register_many(self, extensions: list[str], parser_cls: Type[MediaParser]):
        """Register a parser for many extensions at once"""
        for extension in extensions:
            self.register(extension, parser_cls)

    def unregister(self, extension: str) -> None:
        """Remove a parser class for an extension."""
        extension = extension.lower()
        self._registry.pop(extension, None)

    # ---------------------------------------------------------
    # Lookup
    # ---------------------------------------------------------
    def get(self, extension: str) -> Type[MediaParser] | None:
        """Return the parser class for this extension, or None."""
        return self._registry.get(extension.lower())

    def requires_parser(self, extension: str) -> Type[MediaParser]:
        """Same as get(), but raises if missing."""
        parser_cls = self.get(extension)
        if not parser_cls:
            raise ValueError(f"No MediaParser registered for extension {extension!r}")
        return parser_cls
    
    def get_registered_extensions(self) -> Collection[str]:
        return self._registry.keys()

    # ---------------------------------------------------------
    # Factory
    # ---------------------------------------------------------
    def create_parser(self, extension: str, cacher=None) -> MediaParser:
        """
        Instantiate a MediaParser for a given extension with the provided cacher.
        Passes this registry so parsers that need to resolve other parsers (e.g. PDF) can use it.
        """
        parser_cls = self.requires_parser(extension)
        return parser_cls(cacher=cacher, media_parser_registry=self)


# Create a global registry instance
media_parser_registry = MediaParserRegistry()
