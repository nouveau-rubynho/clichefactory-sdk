"""Unified AI clients for OCR and extraction."""

from clichefactory._engine.ai_clients.protocol import AIClient
from clichefactory._engine.ai_clients.factory import create_ai_client
from clichefactory._engine.ai_clients.prompts import SIMPLE_OCR_PROMPT, DEFAULT_EXTRACTION_PROMPT
from clichefactory._engine.ai_clients.gemini_client import GeminiAIClient
from clichefactory._engine.ai_clients.openai_client import OpenAIAIClient
from clichefactory._engine.ai_clients.anthropic_client import AnthropicAIClient
from clichefactory._engine.ai_clients.ollama_client import OllamaAIClient

__all__ = [
    "AIClient",
    "create_ai_client",
    "SIMPLE_OCR_PROMPT",
    "DEFAULT_EXTRACTION_PROMPT",
    "GeminiAIClient",
    "OpenAIAIClient",
    "AnthropicAIClient",
    "OllamaAIClient",
]
