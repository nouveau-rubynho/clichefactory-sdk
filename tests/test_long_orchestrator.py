"""End-to-end tests for Cliche.extract_long with the transport layer mocked.

We stub ``client.to_markdown_async`` and ``cliche.extract_async(text=...)``
so no LLM / network is involved.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest
from pydantic import BaseModel

from clichefactory import LongExtractionResult, PartialExtraction, factory
from clichefactory.chunking import PageChunker
from clichefactory.resolvers import (
    concat_dedupe,
    first_non_null,
    last_non_null,
    sum_numeric,
)
from clichefactory.errors import LongExtractionError


# ── Fixtures ──────────────────────────────────────────────────────────────


class LineItem(BaseModel):
    description: str
    amount: float


class Invoice(BaseModel):
    invoice_number: str | None = None
    total: float | None = None
    customer_name: str | None = None
    line_items: list[LineItem] = []
    notes: str | None = None


@dataclass
class _FakeDoc:
    markdown: str
    meta: dict[str, Any]

    def get_markdown(self) -> str:
        return self.markdown


def _make_paged_doc(num_pages: int) -> str:
    parts: list[str] = []
    for n in range(1, num_pages + 1):
        parts.append(f"<!-- cf:page {n} -->")
        parts.append(f"\nContent of page {n}.\n")
    return "\n".join(parts)


# ── Core orchestrator behaviour ───────────────────────────────────────────


def test_extract_long_merges_scalars_and_concatenates_lists(monkeypatch):
    client = factory(api_key="dummy", mode="service")
    cliche = client.cliche(
        Invoice,
        resolvers={
            "invoice_number": first_non_null,
            "total": last_non_null,
            "line_items": concat_dedupe(key="description"),
            "customer_name": first_non_null,
        },
    )

    async def fake_to_markdown(*a, **kw):  # noqa: ARG001
        return _FakeDoc(markdown=_make_paged_doc(6), meta={})

    per_chunk_returns = [
        Invoice(
            invoice_number="INV-001",
            total=None,
            customer_name="ACME",
            line_items=[LineItem(description="Widget", amount=10.0)],
            notes=None,
        ),
        Invoice(
            invoice_number=None,
            total=None,
            customer_name="ACME",
            line_items=[LineItem(description="Gadget", amount=20.0)],
            notes=None,
        ),
        Invoice(
            invoice_number=None,
            total=30.0,
            customer_name="ACME",
            line_items=[LineItem(description="Widget", amount=10.0)],  # duplicate
            notes=None,
        ),
    ]

    async def fake_extract(self, *, text, **kwargs):  # noqa: ARG001
        return per_chunk_returns.pop(0)

    monkeypatch.setattr(client, "to_markdown_async", fake_to_markdown)
    from clichefactory.cliche import Cliche

    monkeypatch.setattr(Cliche, "extract_async", fake_extract)

    result = asyncio.run(
        cliche.extract_long_async(
            file=b"ignored",
            chunker=PageChunker(pages_per_chunk=2, overlap_pages=0),
        )
    )

    assert isinstance(result, Invoice)
    assert result.invoice_number == "INV-001"
    assert result.total == 30.0
    assert result.customer_name == "ACME"
    assert len(result.line_items) == 2
    assert {li.description for li in result.line_items} == {"Widget", "Gadget"}


def test_extract_long_include_chunk_results_returns_rich_envelope(monkeypatch):
    client = factory(api_key="dummy", mode="service")
    cliche = client.cliche(
        Invoice,
        resolvers={
            "line_items": concat_dedupe(key="description"),
            "total": sum_numeric,
        },
    )

    async def fake_to_markdown(*a, **kw):  # noqa: ARG001
        return _FakeDoc(markdown=_make_paged_doc(4), meta={})

    responses = [
        Invoice(invoice_number="A", total=10.0, line_items=[LineItem(description="x", amount=10.0)]),
        Invoice(invoice_number=None, total=20.0, line_items=[LineItem(description="y", amount=20.0)]),
    ]

    async def fake_extract(self, *, text, **kwargs):  # noqa: ARG001
        return responses.pop(0)

    monkeypatch.setattr(client, "to_markdown_async", fake_to_markdown)
    from clichefactory.cliche import Cliche

    monkeypatch.setattr(Cliche, "extract_async", fake_extract)

    result = asyncio.run(
        cliche.extract_long_async(
            file=b"ignored",
            chunker=PageChunker(pages_per_chunk=2, overlap_pages=0),
            include_chunk_results=True,
        )
    )

    assert isinstance(result, LongExtractionResult)
    assert isinstance(result.value, Invoice)
    assert len(result.chunks) == 2
    assert "line_items" in result.resolutions
    assert result.resolutions["line_items"].resolver_name == "_fn"  # concat_dedupe closure
    # sum_numeric merged 10 + 20
    assert result.value.total == 30.0
    # cost scaffolding present even without USD data
    assert "by_chunk" in result.cost


def test_extract_long_rejects_unsupported_mode():
    client = factory(api_key="dummy", mode="service")
    cliche = client.cliche(Invoice)
    with pytest.raises(LongExtractionError) as exc:
        asyncio.run(
            cliche.extract_long_async(file=b"x", mode="trained")
        )
    assert exc.value.info.code == "long.unsupported_mode"


def test_extract_long_rejects_artifact_id():
    client = factory(api_key="dummy", mode="service")
    cliche = client.cliche(Invoice, artifact_id="art_123")
    with pytest.raises(LongExtractionError) as exc:
        asyncio.run(cliche.extract_long_async(file=b"x"))
    assert exc.value.info.code == "long.unsupported_mode"


def test_extract_long_default_resolver_for_array_emits_warning(monkeypatch, recwarn):
    client = factory(api_key="dummy", mode="service")
    cliche = client.cliche(Invoice)  # no resolvers configured

    async def fake_to_markdown(*a, **kw):  # noqa: ARG001
        return _FakeDoc(markdown=_make_paged_doc(2), meta={})

    responses = [
        Invoice(line_items=[LineItem(description="x", amount=1.0)]),
        Invoice(line_items=[LineItem(description="y", amount=2.0)]),
    ]

    async def fake_extract(self, *, text, **kwargs):  # noqa: ARG001
        return responses.pop(0)

    monkeypatch.setattr(client, "to_markdown_async", fake_to_markdown)
    from clichefactory.cliche import Cliche

    monkeypatch.setattr(Cliche, "extract_async", fake_extract)

    result = asyncio.run(
        cliche.extract_long_async(
            file=b"x",
            chunker=PageChunker(pages_per_chunk=1, overlap_pages=0),
        )
    )
    assert isinstance(result, Invoice)
    assert len(result.line_items) == 2  # concatenated by default
    warn_msgs = [str(w.message) for w in recwarn.list]
    assert any("line_items" in m and "concat_dedupe" in m for m in warn_msgs)


def test_extract_long_tolerates_some_chunk_failures(monkeypatch):
    client = factory(api_key="dummy", mode="service")
    cliche = client.cliche(
        Invoice,
        resolvers={"invoice_number": first_non_null, "line_items": concat_dedupe(key="description")},
    )

    async def fake_to_markdown(*a, **kw):  # noqa: ARG001
        return _FakeDoc(markdown=_make_paged_doc(3), meta={})

    call = {"i": 0}

    async def fake_extract(self, *, text, **kwargs):  # noqa: ARG001
        call["i"] += 1
        if call["i"] == 2:
            raise RuntimeError("chunk 2 boom")
        return Invoice(invoice_number="INV-1", line_items=[LineItem(description="x", amount=1.0)])

    monkeypatch.setattr(client, "to_markdown_async", fake_to_markdown)
    from clichefactory.cliche import Cliche

    monkeypatch.setattr(Cliche, "extract_async", fake_extract)

    result = asyncio.run(
        cliche.extract_long_async(
            file=b"x",
            chunker=PageChunker(pages_per_chunk=1, overlap_pages=0),
            include_chunk_results=True,
        )
    )
    assert isinstance(result, LongExtractionResult)
    assert result.value.invoice_number == "INV-1"
    assert any("failed" in w for w in result.warnings)


def test_extract_long_raises_when_all_chunks_fail(monkeypatch):
    client = factory(api_key="dummy", mode="service")
    cliche = client.cliche(Invoice)

    async def fake_to_markdown(*a, **kw):  # noqa: ARG001
        return _FakeDoc(markdown=_make_paged_doc(2), meta={})

    async def fake_extract(self, *, text, **kwargs):  # noqa: ARG001
        raise RuntimeError("everything is on fire")

    monkeypatch.setattr(client, "to_markdown_async", fake_to_markdown)
    from clichefactory.cliche import Cliche

    monkeypatch.setattr(Cliche, "extract_async", fake_extract)

    with pytest.raises(LongExtractionError) as exc:
        asyncio.run(
            cliche.extract_long_async(
                file=b"x",
                chunker=PageChunker(pages_per_chunk=1, overlap_pages=0),
            )
        )
    assert exc.value.info.code == "long.all_chunks_failed"


def test_extract_long_per_call_resolvers_override_cliche_level(monkeypatch):
    client = factory(api_key="dummy", mode="service")
    cliche = client.cliche(
        Invoice,
        resolvers={"invoice_number": first_non_null},
    )

    async def fake_to_markdown(*a, **kw):  # noqa: ARG001
        return _FakeDoc(markdown=_make_paged_doc(3), meta={})

    responses = [
        Invoice(invoice_number="A"),
        Invoice(invoice_number="B"),
        Invoice(invoice_number="C"),
    ]

    async def fake_extract(self, *, text, **kwargs):  # noqa: ARG001
        return responses.pop(0)

    monkeypatch.setattr(client, "to_markdown_async", fake_to_markdown)
    from clichefactory.cliche import Cliche

    monkeypatch.setattr(Cliche, "extract_async", fake_extract)

    # Per-call override: pick the last non-null instead of the first.
    result = asyncio.run(
        cliche.extract_long_async(
            file=b"x",
            chunker=PageChunker(pages_per_chunk=1, overlap_pages=0),
            resolvers={"invoice_number": last_non_null},
        )
    )
    assert result.invoice_number == "C"


def test_extract_long_empty_chunker_output_raises(monkeypatch):
    client = factory(api_key="dummy", mode="service")
    cliche = client.cliche(Invoice)

    async def fake_to_markdown(*a, **kw):  # noqa: ARG001
        return _FakeDoc(markdown="", meta={})

    monkeypatch.setattr(client, "to_markdown_async", fake_to_markdown)
    with pytest.raises(LongExtractionError) as exc:
        asyncio.run(cliche.extract_long_async(file=b"x"))
    assert exc.value.info.code == "long.no_chunks"


def test_extract_long_handles_partial_extraction_from_chunk(monkeypatch):
    client = factory(api_key="dummy", mode="service")
    cliche = client.cliche(
        Invoice,
        resolvers={"invoice_number": first_non_null},
    )

    async def fake_to_markdown(*a, **kw):  # noqa: ARG001
        return _FakeDoc(markdown=_make_paged_doc(2), meta={})

    responses: list[Any] = [
        PartialExtraction(raw={"invoice_number": "INV-P"}, validation_errors=[{"type": "x"}]),
        Invoice(invoice_number=None),
    ]

    async def fake_extract(self, *, text, **kwargs):  # noqa: ARG001
        return responses.pop(0)

    monkeypatch.setattr(client, "to_markdown_async", fake_to_markdown)
    from clichefactory.cliche import Cliche

    monkeypatch.setattr(Cliche, "extract_async", fake_extract)

    result = asyncio.run(
        cliche.extract_long_async(
            file=b"x",
            chunker=PageChunker(pages_per_chunk=1, overlap_pages=0),
        )
    )
    assert result.invoice_number == "INV-P"
