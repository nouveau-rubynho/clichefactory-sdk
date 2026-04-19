"""Public chunk strategies for :meth:`clichefactory.Cliche.extract_long`.

Example::

    from clichefactory import factory
    from clichefactory.chunking import PageChunker

    client = factory(api_key=..., model=Endpoint(provider_model="openai/gpt-5"))
    cliche = client.cliche(Invoice)
    result = cliche.extract_long(
        file="long_contract.pdf",
        chunker=PageChunker(pages_per_chunk=15, overlap_pages=1),
    )
"""
from __future__ import annotations

from clichefactory._chunking import (
    ChunkStrategy,
    HeadingChunker,
    PageChunker,
    TokenChunker,
)

__all__ = [
    "ChunkStrategy",
    "HeadingChunker",
    "PageChunker",
    "TokenChunker",
]
