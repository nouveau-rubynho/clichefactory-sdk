"""Tests for graceful MIME degrade in the fast (one-shot) extract path.

Covers:

* :func:`is_default_direct_bytes_mime` and :func:`client_supports_bytes`
* Per-client :meth:`AIClient.supports_bytes` correctness
* Per-client :meth:`AIClient.extract_from_bytes` precondition (raises
  :class:`UnsupportedBytesMimeError` for unsupported MIMEs, before any
  network call)
* :func:`extract_local` fast-path routing — PDF goes through bytes,
  EML / DOCX degrade to markdown → ``client.extract(text, schema)``
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from clichefactory._engine.ai_clients import (
    AnthropicAIClient,
    GeminiAIClient,
    OllamaAIClient,
    OpenAIAIClient,
    UnsupportedBytesMimeError,
    client_supports_bytes,
    is_default_direct_bytes_mime,
)


class _Doc(BaseModel):
    title: str = "ok"


# ── helpers / fakes ──────────────────────────────────────────────────────


class _FakeClientNoSupports:
    """AIClient stand-in without ``supports_bytes`` (BYO client)."""

    def extract(self, text, schema, prompt=None, *, raise_on_validation_error=True):
        return schema.model_validate({"title": "from-text"})

    def extract_from_bytes(
        self, content, mime, schema, prompt=None, *, raise_on_validation_error=True
    ):
        return schema.model_validate({"title": "from-bytes"})


class _FakeClient:
    """AIClient stand-in with a configurable ``supports_bytes``."""

    def __init__(self, *, supported: set[str] | None = None) -> None:
        self.supported = supported or {"application/pdf"}
        self.calls: list[tuple[str, dict]] = []

    def supports_bytes(self, mime: str) -> bool:
        return mime in self.supported

    def extract(self, text, schema, prompt=None, *, raise_on_validation_error=True):
        self.calls.append(("extract", {"text_len": len(text or "")}))
        return schema.model_validate({"title": "from-text"})

    def extract_from_bytes(
        self, content, mime, schema, prompt=None, *, raise_on_validation_error=True
    ):
        self.calls.append(("extract_from_bytes", {"mime": mime}))
        return schema.model_validate({"title": "from-bytes"})


# ── unit: helper functions ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "mime,expected",
    [
        ("application/pdf", True),
        ("image/png", True),
        ("image/jpeg", True),
        ("image/jpg", True),
        ("image/webp", True),
        ("image/gif", True),
        ("IMAGE/PNG", True),
        ("application/pdf; charset=utf-8", True),
        ("message/rfc822", False),
        (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            False,
        ),
        ("application/vnd.ms-excel", False),
        ("text/csv", False),
        ("text/plain", False),
        ("application/octet-stream", False),
        ("", False),
        (None, False),
    ],
)
def test_is_default_direct_bytes_mime(mime, expected) -> None:
    assert is_default_direct_bytes_mime(mime) is expected


def test_client_supports_bytes_uses_method_when_present() -> None:
    fake = _FakeClient(supported={"application/pdf"})
    assert client_supports_bytes(fake, "application/pdf") is True
    assert client_supports_bytes(fake, "message/rfc822") is False


def test_client_supports_bytes_falls_back_to_default_when_method_missing() -> None:
    fake = _FakeClientNoSupports()
    assert client_supports_bytes(fake, "application/pdf") is True
    assert client_supports_bytes(fake, "image/png") is True
    assert client_supports_bytes(fake, "message/rfc822") is False


def test_client_supports_bytes_swallows_method_exception() -> None:
    class Boom:
        def supports_bytes(self, mime: str) -> bool:
            raise RuntimeError("oops")

    assert client_supports_bytes(Boom(), "application/pdf") is True
    assert client_supports_bytes(Boom(), "message/rfc822") is False


# ── unit: per-client supports_bytes + precondition ───────────────────────


def _make_gemini() -> GeminiAIClient:
    return GeminiAIClient(model_name="gemini/gemini-2.5-flash", api_key="dummy")


def _make_openai() -> OpenAIAIClient:
    return OpenAIAIClient(model_name="openai/gpt-4o-mini", api_key="dummy")


def _make_anthropic() -> AnthropicAIClient:
    return AnthropicAIClient(model_name="anthropic/claude-3-5-haiku", api_key="dummy")


def _make_ollama() -> OllamaAIClient:
    return OllamaAIClient(model_name="ollama/llama3.1")


@pytest.mark.parametrize(
    "make_client,vendor",
    [
        (_make_gemini, "Gemini"),
        (_make_openai, "OpenAI"),
        (_make_anthropic, "Anthropic"),
    ],
)
def test_hosted_clients_support_pdf_and_images(make_client, vendor) -> None:
    c = make_client()
    assert c.supports_bytes("application/pdf") is True
    assert c.supports_bytes("image/png") is True
    assert c.supports_bytes("image/jpeg") is True
    assert c.supports_bytes("image/webp") is True
    assert c.supports_bytes("image/gif") is True


@pytest.mark.parametrize(
    "make_client",
    [_make_gemini, _make_openai, _make_anthropic],
)
def test_hosted_clients_reject_unsupported_mimes(make_client) -> None:
    c = make_client()
    assert c.supports_bytes("message/rfc822") is False
    assert c.supports_bytes("application/vnd.ms-excel") is False
    assert (
        c.supports_bytes(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        is False
    )


def test_ollama_never_supports_bytes() -> None:
    c = _make_ollama()
    assert c.supports_bytes("application/pdf") is False
    assert c.supports_bytes("image/png") is False
    assert c.supports_bytes("message/rfc822") is False


@pytest.mark.parametrize(
    "make_client,vendor",
    [
        (_make_gemini, "Gemini"),
        (_make_openai, "OpenAI"),
        (_make_anthropic, "Anthropic"),
    ],
)
def test_extract_from_bytes_raises_clean_error_for_unsupported_mime(
    make_client, vendor
) -> None:
    c = make_client()
    with pytest.raises(UnsupportedBytesMimeError) as excinfo:
        c.extract_from_bytes(
            content=b"From: a@b\r\nTo: c@d\r\nSubject: hi\r\n\r\nbody",
            mime="message/rfc822",
            schema=_Doc,
        )
    assert excinfo.value.mime == "message/rfc822"
    assert excinfo.value.vendor == vendor


# ── integration: extract_local fast path ─────────────────────────────────


def _run(coro):
    return asyncio.run(coro)


def test_fast_pdf_uses_extract_from_bytes(tmp_path) -> None:
    """PDF in fast mode should use ``extract_from_bytes`` (no markdown step)."""
    from clichefactory._local import extract_local

    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4\n% fake\n")

    fake = _FakeClient(supported={"application/pdf"})

    async def _go():
        with patch(
            "clichefactory._engine.ai_clients.create_ai_client", return_value=fake
        ):
            return await extract_local(
                schema=_Doc,
                file=str(pdf),
                text=None,
                filename="doc.pdf",
                file_type=None,
                mode="fast",
                parsing=None,
                llm=MagicMock(),
                ocr_llm=None,
                include_doc=False,
                include_costs=False,
                postprocess=None,
                allow_partial=False,
            )

    out = _run(_go())
    assert isinstance(out, _Doc)
    assert out.title == "from-bytes"
    method_names = [c[0] for c in fake.calls]
    assert method_names == ["extract_from_bytes"]
    assert fake.calls[0][1]["mime"] == "application/pdf"


def test_fast_eml_degrades_to_markdown_then_extract(tmp_path) -> None:
    """EML in fast mode should parse → markdown → ``extract(text, schema)``."""
    from clichefactory._local import extract_local

    eml = tmp_path / "msg.eml"
    eml.write_bytes(
        b"From: a@b\r\nTo: c@d\r\nSubject: hello\r\n\r\nbody text\r\n"
    )

    fake = _FakeClient(supported={"application/pdf", "image/png"})

    fake_doc = MagicMock()
    fake_doc.get_markdown.return_value = "# Subject: hello\n\nbody text"

    async def _fake_to_markdown(**kwargs):
        return fake_doc

    async def _go():
        with patch(
            "clichefactory._engine.ai_clients.create_ai_client", return_value=fake
        ), patch(
            "clichefactory._local.to_markdown_local",
            new=AsyncMock(side_effect=_fake_to_markdown),
        ):
            return await extract_local(
                schema=_Doc,
                file=str(eml),
                text=None,
                filename="msg.eml",
                file_type=None,
                mode="fast",
                parsing=None,
                llm=MagicMock(),
                ocr_llm=None,
                include_doc=False,
                include_costs=False,
                postprocess=None,
                allow_partial=False,
            )

    out = _run(_go())
    assert isinstance(out, _Doc)
    assert out.title == "from-text"
    method_names = [c[0] for c in fake.calls]
    assert method_names == ["extract"]
    assert fake.calls[0][1]["text_len"] > 0
    fake_doc.get_markdown.assert_called_once()


def test_fast_docx_degrades_to_markdown_then_extract(tmp_path) -> None:
    """DOCX in fast mode should also degrade — same code path as EML."""
    from clichefactory._local import extract_local

    docx = tmp_path / "report.docx"
    docx.write_bytes(b"PK\x03\x04fake-docx")

    fake = _FakeClient(supported={"application/pdf", "image/png"})

    fake_doc = MagicMock()
    fake_doc.get_markdown.return_value = "# Report\n\nlorem ipsum"

    async def _fake_to_markdown(**kwargs):
        return fake_doc

    async def _go():
        with patch(
            "clichefactory._engine.ai_clients.create_ai_client", return_value=fake
        ), patch(
            "clichefactory._local.to_markdown_local",
            new=AsyncMock(side_effect=_fake_to_markdown),
        ):
            return await extract_local(
                schema=_Doc,
                file=str(docx),
                text=None,
                filename="report.docx",
                file_type=None,
                mode="fast",
                parsing=None,
                llm=MagicMock(),
                ocr_llm=None,
                include_doc=False,
                include_costs=False,
                postprocess=None,
                allow_partial=False,
            )

    out = _run(_go())
    assert isinstance(out, _Doc)
    method_names = [c[0] for c in fake.calls]
    assert method_names == ["extract"]
