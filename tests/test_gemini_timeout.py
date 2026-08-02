from unittest.mock import Mock, patch

import pytest
import requests

from linkedin_ai_agent.gemini_client import GeminiClient, gemini_retry_delay


class FakeResponse:
    def __init__(self, status_code, payload, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.ok = 200 <= status_code < 300
        self.text = str(payload)

    def json(self):
        return self._payload


def test_post_json_retries_timeout_then_reports(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    client = GeminiClient()
    with patch("linkedin_ai_agent.gemini_client.requests.post", side_effect=requests.Timeout("slow")):
        with pytest.raises(RuntimeError, match="timed out"):
            client._post_json("https://example.com", {}, timeout=1)


def test_post_json_honors_structured_gemini_retry_delay(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    client = GeminiClient()
    limited = FakeResponse(
        429,
        {
            "error": {
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.RetryInfo",
                        "retryDelay": "53.334865113s",
                    }
                ]
            }
        },
    )
    success = FakeResponse(200, {"ok": True})

    with patch("linkedin_ai_agent.gemini_client.requests.post", side_effect=[limited, success]):
        with patch("linkedin_ai_agent.gemini_client.time.sleep") as sleep:
            assert client._post_json("https://example.com", {}, timeout=1) == {"ok": True}

    sleep.assert_called_once_with(54)


def test_retry_delay_reads_message_and_caps_long_wait():
    response = FakeResponse(429, {"error": {"message": "Please retry in 93.2s."}})

    assert gemini_retry_delay(response, fallback_seconds=1) == 60
