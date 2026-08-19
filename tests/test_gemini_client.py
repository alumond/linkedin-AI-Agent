from pathlib import Path

from PIL import Image

from linkedin_ai_agent.gemini_client import extract_citations, output_text_from_interaction, post_length_target
from linkedin_ai_agent.models import DraftPost
from tests.test_ranking import config


def test_interaction_helpers_accept_step_list_response():
    response = [
        {
            "type": "model_output",
            "content": [
                {
                    "type": "text",
                    "text": "hello",
                    "annotations": [
                        {
                            "type": "url_citation",
                            "title": "Example",
                            "url": "https://example.com",
                            "start_index": 0,
                            "end_index": 5,
                        }
                    ],
                }
            ],
        }
    ]
    assert output_text_from_interaction(response) == "hello"
    assert extract_citations(response)[0]["url"] == "https://example.com"


def test_post_length_target_keeps_buffer_inside_hard_limits(tmp_path):
    assert post_length_target(config(tmp_path)) == (210, 350)


def test_generate_illustration_prompt_uses_readable_infographic_standard(tmp_path):
    class CapturingGemini:
        def __init__(self):
            self.payload = None

        def generate_illustration(self, cfg, draft, output_path):
            from linkedin_ai_agent.gemini_client import GeminiClient

            client = GeminiClient.__new__(GeminiClient)

            def fake_generate_content(model, payload):
                self.payload = payload
                image_path = tmp_path / "source.png"
                Image.new("RGB", (16, 16), "white").save(image_path)
                return {
                    "candidates": [
                        {
                            "content": {
                                "parts": [
                                    {
                                        "inline_data": {
                                            "mime_type": "image/png",
                                            "data": image_path.read_bytes().hex(),
                                        }
                                    }
                                ]
                            }
                        }
                    ]
                }

            client._generate_content = fake_generate_content
            return GeminiClient.generate_illustration(client, cfg, draft, output_path)

    # Patch the response helper to accept deterministic hex bytes for this prompt-only test.
    import linkedin_ai_agent.gemini_client as module

    original = module.image_bytes_from_generate_content
    module.image_bytes_from_generate_content = lambda response: bytes.fromhex(
        response["candidates"][0]["content"]["parts"][0]["inline_data"]["data"]
    )
    try:
        gemini = CapturingGemini()
        draft = DraftPost(
            topic="Analytics workflow",
            category="analytics",
            body="Turn raw data into a clear business decision.",
            hashtags=[],
            primary_source_url="",
            supporting_source_urls=[],
            claims=[],
            visual_style="illustration",
            visual_prompt="Show the workflow clearly.",
            alt_text="Workflow infographic",
        )
        gemini.generate_illustration(config(tmp_path), draft, tmp_path / "out.png")
    finally:
        module.image_bytes_from_generate_content = original

    prompt = gemini.payload["contents"][0]["parts"][0]["text"]
    assert "premium LinkedIn infographic" in prompt
    assert "short readable captions" in prompt
    assert "Choose square or landscape format" in prompt
    assert "All text must be correctly spelled" in prompt
    assert "no readable words" not in prompt.lower()
    assert "aspect_ratio" not in gemini.payload.get("generationConfig", {}).get("image_config", {})
