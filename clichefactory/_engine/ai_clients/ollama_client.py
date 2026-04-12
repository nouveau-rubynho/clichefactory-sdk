"""
Ollama implementation of AIClient.
MVP scope: extraction from text only (no OCR / bytes extraction).
"""
from __future__ import annotations

import json
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from clichefactory._engine.ai_clients.prompts import DEFAULT_EXTRACTION_PROMPT
from clichefactory._engine.ai_clients.json_utils import safe_json_loads
from clichefactory._extract_validation import RawExtractionValidationError, validate_or_raise_raw

T = TypeVar("T", bound=BaseModel)


def _model_name_for_ollama(name: str) -> str:
    """Strip 'ollama/' prefix if present."""
    if name.startswith("ollama/"):
        return name[len("ollama/") :].strip()
    return name.strip()


class OllamaAIClient:
    """AIClient implementation using native Ollama chat API."""

    def __init__(
        self,
        model_name: str,
        api_base: str = "http://localhost:11434",
        api_key: str = "",
        timeout_seconds: float = 120.0,
        max_retries: int = 3,
    ) -> None:
        self._model_name = _model_name_for_ollama(model_name)
        self._full_model_name = (
            model_name if model_name.startswith("ollama/") else f"ollama/{model_name}"
        )
        self._api_base = api_base.rstrip("/")
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries

    def set_cost_tracker(self, _cost_tracker: Any) -> None:
        """No-op for Ollama MVP (no usage tracking)."""
        return

    def _chat(self, prompt: str) -> str:
        headers: dict[str, str] = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        payload = {
            "model": self._model_name,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        with httpx.Client(timeout=self._timeout_seconds) as client:
            response = client.post(
                f"{self._api_base}/api/chat",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
        message = data.get("message") or {}
        content = message.get("content")
        if not isinstance(content, str):
            raise ValueError("Ollama response did not contain message.content text.")
        return content.strip()

    def ocr(self, content: bytes, mime: str, prompt: str) -> str:
        raise NotImplementedError(
            "OllamaAIClient OCR is not supported in MVP. "
            "Use gemini/openai/anthropic for OCR or a non-LLM OCR parser."
        )

    def ocr_pages(
        self, content: bytes, page_numbers: list[int], prompt: str
    ) -> dict[int, str]:
        raise NotImplementedError(
            "OllamaAIClient ocr_pages is not supported in MVP."
        )

    def ocr_images(
        self, prompt: str, images: list[bytes], mime: str = "image/png"
    ) -> str:
        raise NotImplementedError(
            "OllamaAIClient ocr_images is not supported in MVP."
        )

    def ocr_batch(
        self, items: list[tuple[bytes, str]], prompt: str
    ) -> list[str]:
        raise NotImplementedError(
            "OllamaAIClient ocr_batch is not supported in MVP."
        )

    def extract(
        self,
        text: str,
        schema: type[T],
        prompt: str | None = None,
        *,
        raise_on_validation_error: bool = True,
    ) -> T:
        """Extract JSON matching schema from text with validation retries."""
        instr = prompt or DEFAULT_EXTRACTION_PROMPT
        schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False)
        full_prompt = (
            f"{instr}\n\n"
            "You must return only valid JSON object that conforms to this JSON Schema:\n"
            f"{schema_json}\n\n"
            f"Document:\n{text}"
        )

        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                raw = self._chat(full_prompt)
                data = safe_json_loads(
                    raw,
                    error_prefix="Ollama returned invalid JSON for schema extraction",
                )
                return validate_or_raise_raw(
                    schema, data, raise_on_validation_error=raise_on_validation_error
                )
            except RawExtractionValidationError:
                raise
            except (json.JSONDecodeError, ValueError) as exc:
                last_error = exc
                full_prompt += (
                    "\n\nYour previous answer was invalid. "
                    "Return ONLY a strict JSON object matching the schema."
                )
                if attempt == self._max_retries:
                    break

        raise ValueError(
            f"Ollama extraction failed after {self._max_retries} attempts: {last_error}"
        )

    def extract_json(self, text: str, prompt: str) -> dict:
        """Schema-less JSON extraction: prompt + document text -> plain dict."""
        full_prompt = (
            f"{prompt}\n\n"
            "You must return only a valid JSON object.\n\n"
            f"Document:\n{text}"
        )
        raw = self._chat(full_prompt)
        return safe_json_loads(
            raw,
            error_prefix="Ollama returned invalid JSON for freeform extraction",
        )

    def extract_from_bytes(
        self,
        content: bytes,
        mime: str,
        schema: type[T],
        prompt: str | None = None,
        **kwargs: Any,
    ) -> T:
        raise NotImplementedError(
            "OllamaAIClient extract_from_bytes is not supported in MVP. "
            "Run OCR first, then call extract(text, schema)."
        )
