"""Gemini client routes OCR vs extraction token usage to the correct tracker methods."""
from unittest.mock import MagicMock

from clichefactory._engine.ai_clients.gemini_client import GeminiAIClient


def _fake_response_with_usage(pt: int = 10, ct: int = 5) -> MagicMock:
    um = MagicMock()
    um.prompt_token_count = pt
    um.candidates_token_count = ct
    um.total_token_count = pt + ct
    resp = MagicMock()
    resp.usage_metadata = um
    return resp


def test_record_usage_ocr_calls_add_ocr_usage():
    tracker = MagicMock()
    client = GeminiAIClient(model_name="gemini/gemini-2.0-flash", api_key="test-key")
    client.set_cost_tracker(tracker)
    client._record_usage(_fake_response_with_usage(), phase="ocr")
    tracker.add_ocr_usage.assert_called_once()
    tracker.add_extraction_usage.assert_not_called()


def test_record_usage_extraction_calls_add_extraction_usage():
    tracker = MagicMock()
    client = GeminiAIClient(model_name="gemini/gemini-2.0-flash", api_key="test-key")
    client.set_cost_tracker(tracker)
    client._record_usage(_fake_response_with_usage(), phase="extraction")
    tracker.add_extraction_usage.assert_called_once()
    tracker.add_ocr_usage.assert_not_called()
