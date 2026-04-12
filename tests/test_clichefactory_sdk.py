from __future__ import annotations

import pytest
from pydantic import BaseModel

from clichefactory import Endpoint, factory
from clichefactory.errors import UnsupportedModeError, UnsupportedParserError


class _Invoice(BaseModel):
    invoice_number: str | None = None
    total_amount: float | None = None


def test_extract_from_text_local():
    client = factory(
        mode="local",
        llm=Endpoint(provider_model="ollama/llama3.2:1b", api_key="", api_base="http://localhost:11434"),
    )
    c = client.cliche(_Invoice)

    # Patch underlying Ollama client network call by monkeypatching _chat.
    from clichefactory._engine.ai_clients.ollama_client import OllamaAIClient

    orig = OllamaAIClient._chat
    try:
        OllamaAIClient._chat = lambda self, prompt: '{"invoice_number":"123","total_amount":99.0}'
        out = c.extract(text="Invoice 123 total 99")
        assert out.invoice_number == "123"
        assert out.total_amount == 99.0
    finally:
        OllamaAIClient._chat = orig


def test_local_blocks_saas_only_modes():
    client = factory(
        mode="local",
        llm=Endpoint(provider_model="ollama/llama3.2:1b", api_key="", api_base="http://localhost:11434"),
    )
    c = client.cliche(_Invoice)

    with pytest.raises(UnsupportedModeError) as e:
        c.extract(text="x", mode="robust")
    assert e.value.info.code == "mode.unsupported_local"


def test_local_blocks_vision_layout_parser():
    from clichefactory import ParsingOptions

    client = factory(
        mode="local",
        llm=Endpoint(provider_model="ollama/llama3.2:1b", api_key="", api_base="http://localhost:11434"),
        parsing=ParsingOptions(pdf_image_parser="vision_layout"),
    )

    with pytest.raises(UnsupportedParserError) as e:
        client.to_markdown(file=b"hi", filename="x.pdf")
    assert e.value.info.code == "parser.unsupported_local"

