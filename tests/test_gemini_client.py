from linkedin_ai_agent.gemini_client import extract_citations, output_text_from_interaction


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
