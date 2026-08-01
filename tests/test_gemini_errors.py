from linkedin_ai_agent.gemini_client import gemini_error_message


class FakeResponse:
    status_code = 400
    text = "[bad]"

    def json(self):
        return [{"error": "bad"}]


def test_gemini_error_message_accepts_list_json():
    message = gemini_error_message(FakeResponse())
    assert "HTTP 400" in message
    assert "bad" in message
