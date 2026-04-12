from __future__ import annotations

import pytest
from pydantic import BaseModel

from clichefactory._engine.ai_clients.ollama_client import OllamaAIClient


class _Person(BaseModel):
    name: str


def test_extract_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch):
    client = OllamaAIClient(
        model_name="ollama/llama3.2:1b",
        max_retries=2,
    )
    responses = iter(
        [
            "not-a-json-response",
            '{"name":"Bob"}',
        ]
    )

    monkeypatch.setattr(client, "_chat", lambda _prompt: next(responses))
    out = client.extract("Document text", _Person)
    assert out.name == "Bob"


def test_extract_retries_then_fails(monkeypatch: pytest.MonkeyPatch):
    client = OllamaAIClient(
        model_name="ollama/llama3.2:1b",
        max_retries=2,
    )
    calls = {"n": 0}

    def _bad_chat(_prompt: str) -> str:
        calls["n"] += 1
        return "still not json"

    monkeypatch.setattr(client, "_chat", _bad_chat)

    with pytest.raises(ValueError, match="failed after 2 attempts"):
        client.extract("Document text", _Person)
    assert calls["n"] == 2
