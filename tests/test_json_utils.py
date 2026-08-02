from linkedin_ai_agent.json_utils import parse_json_object


def test_parse_json_object_from_fenced_text():
    assert parse_json_object('```json\n{"ok": true}\n```') == {"ok": True}


def test_parse_json_object_from_surrounding_text():
    assert parse_json_object('Result:\n{"items": [1, 2]}') == {"items": [1, 2]}
