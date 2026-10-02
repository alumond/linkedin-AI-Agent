from unittest.mock import Mock

import pytest
from PIL import Image

from linkedin_ai_agent.linkedin_client import LinkedInClient
from linkedin_ai_agent.validators import validate_visual


def test_high_resolution_png_upload_preserves_exact_source_bytes(tmp_path, monkeypatch):
    path = tmp_path / 'capture.png'
    Image.new('RGB', (4800, 3360), '#191b1e').save(path)
    original = path.read_bytes()
    visual = validate_visual(path, 'Sample app screen.', allow_screenshot=True)
    client = LinkedInClient('test-only-token', Mock())
    monkeypatch.setattr(client, 'initialize_image_upload', lambda: ('https://upload.example/image', 'urn:li:image:test'))
    upload = Mock()
    monkeypatch.setattr('linkedin_ai_agent.linkedin_client._request_with_retries', upload)

    assert client.upload_image(visual) == 'urn:li:image:test'
    assert (visual.width, visual.height) == (4800, 3360)
    assert upload.call_args.kwargs['data'] == original
    assert upload.call_args.kwargs['headers']['Content-Type'] == 'image/png'
    assert path.read_bytes() == original


def test_image_at_linkedin_pixel_limit_is_rejected(tmp_path):
    path = tmp_path / 'oversized.png'
    # Exactly 36,152,320 pixels; the platform requires strictly fewer.
    Image.new('RGB', (5120, 7061), 'white').save(path)
    with pytest.raises(ValueError, match='fewer than 36,152,320'):
        validate_visual(path, 'Oversized app screen.', allow_screenshot=True)
