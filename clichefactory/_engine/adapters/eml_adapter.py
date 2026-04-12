from typing import Sequence

from clichefactory._engine.models.document_model import Image, Page, Section, Table
from clichefactory._engine.models.normalized_doc import NormalizedDoc


class EmlDoc(NormalizedDoc):
    summary_text: str
    media_type: str
    pages: Sequence[Page]
    sections: Sequence[Section]

    # Internal fields
    _plain_text: str
    _markdown: str
    _images: Sequence[Image]
    _tables: Sequence[Table]

    def __init__(
        self,
        summary_text: str,
        media_type: str,
        pages: Sequence[Page],
        sections: Sequence[Section],
        images: Sequence[Image],
        tables: Sequence[Table],
        _plain_text: str,
        _markdown: str
        ) -> None:
        
        self.summary_text = summary_text
        self.media_type = media_type
        self.pages = pages
        self.sections = sections
        self.images = images
        self.tables = tables
        self._plain_text = _plain_text
        self._markdown = _markdown


    def get_plain_text(self) -> str:
        return self._plain_text

    def get_markdown(self) -> str:
        return self._markdown
