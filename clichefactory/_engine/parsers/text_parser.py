from __future__ import annotations

from typing import Any

from clichefactory._engine.models.document_model import Heading, Page, Paragraph
from clichefactory._engine.models.normalized_doc import NormalizedDoc
from clichefactory._engine.parsers.media_parser import MediaParser


class TextNormalizedDoc(NormalizedDoc):
    def __init__(self, filename: str, markdown: str) -> None:
        self.filename = filename
        self.summary_text = ""
        self.markdown = markdown
        self.pages = (Page(index=1, size=None, blocks=(Heading(level=1, text=filename), Paragraph(text=markdown))),)
        self.sections = tuple()
        self.images = tuple()
        self.tables = tuple()

    def get_plain_text(self) -> str:
        return self.markdown

    def get_markdown(self) -> str:
        return self.markdown


class TextParser(MediaParser):
    """
    .txt/.md -> TextNormalizedDoc

    Keeps content as markdown-ish text; does not attempt table inference.
    """

    def __init__(self, cacher=None, **kwargs: Any) -> None:
        super().__init__(cacher=cacher, **kwargs)

    def document_parse(self, content: bytes, filename: str) -> NormalizedDoc:
        # Pragmatic decoding.
        for enc in ("utf-8", "utf-8-sig", "latin-1"):
            try:
                s = content.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        else:
            s = content.decode("utf-8", errors="replace")
        md = s.strip()
        if not md:
            md = "_Empty file_"
        return TextNormalizedDoc(filename=filename or "text", markdown=md + "\n")

