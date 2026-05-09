"""Unified AI clients for OCR and extraction."""

from clichefactory._engine.ai_clients.protocol import AIClient, UnsupportedBytesMimeError
from clichefactory._engine.ai_clients.factory import create_ai_client
from clichefactory._engine.ai_clients.mime_support import (
    DEFAULT_DIRECT_BYTES_MIMES,
    client_supports_bytes,
    is_default_direct_bytes_mime,
)
from clichefactory._engine.ai_clients.prompts import SIMPLE_OCR_PROMPT, DEFAULT_EXTRACTION_PROMPT
from clichefactory._engine.ai_clients.gemini_client import GeminiAIClient
from clichefactory._engine.ai_clients.openai_client import OpenAIAIClient
from clichefactory._engine.ai_clients.anthropic_client import AnthropicAIClient
from clichefactory._engine.ai_clients.ollama_client import OllamaAIClient

__all__ = [
    "AIClient",
    "AnthropicAIClient",
    "DEFAULT_DIRECT_BYTES_MIMES",
    "DEFAULT_EXTRACTION_PROMPT",
    "GeminiAIClient",
    "OllamaAIClient",
    "OpenAIAIClient",
    "SIMPLE_OCR_PROMPT",
    "UnsupportedBytesMimeError",
    "client_supports_bytes",
    "create_ai_client",
    "is_default_direct_bytes_mime",
]
