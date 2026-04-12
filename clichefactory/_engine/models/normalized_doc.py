from __future__ import annotations
from abc import ABC, abstractmethod
import pickle
from typing import TYPE_CHECKING, Sequence
from clichefactory._engine.models.document_model import Image, Page, Section, Table

if TYPE_CHECKING:
    from clichefactory._engine.models.usage_summary import UsageSummary


class NormalizedDoc(ABC):
    filename: str | None
    summary_text: str
    media_type: str                 # "application/octet-stream"
    pages: Sequence[Page]           # Layout model of the document
    sections: Sequence[Section]     # Semantic model
    images: Sequence[Image]
    tables: Sequence[Table]
    cost_summary: "UsageSummary | None" = None  # Optional server-provided usage summary

    @abstractmethod
    def get_plain_text(self) -> str: 
        ...

    @abstractmethod
    def get_markdown(self) -> str: 
        ...

    def get_pages(self) -> Sequence[Page]:
        return self.pages

    def get_sections(self) -> Sequence[Section]:
        return self.sections

    def get_images(self) -> Sequence[Image]:
        return self.images

    def get_tables(self) -> Sequence[Table]:
        return self.tables

    # ---- Concrete serialization / deserialization ----
    def serialize(self) -> bytes:
        """
        Default binary serialization for caching.
        Subclasses can override if they want JSON or something else.
        """
        return pickle.dumps(self)

    @classmethod
    def deserialize(cls, data: bytes) -> "NormalizedDoc":
        """
        Default deserialization. Note that this trusts the pickled type,
        which can be any subclass of NormalizedDoc.
        """
        obj = pickle.loads(data)
        if not isinstance(obj, NormalizedDoc):
            raise TypeError(
                f"Deserialized object is not a NormalizedDoc (got {type(obj)!r})"
            )
        return obj