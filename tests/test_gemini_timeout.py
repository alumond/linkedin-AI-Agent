from unittest.mock import Mock, patch

import pytest
import requests

from linkedin_ai_agent.gemini_client import GeminiClient


def test_post_json_retries_timeout_then_reports(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    client = GeminiClient()
    with patch("linkedin_ai_agent.gemini_client.requests.post", side_effect=requests.Timeout("slow")):
        with pytest.raises(RuntimeError, match="timed out"):
            client._post_json("https://example.com", {}, timeout=1)
