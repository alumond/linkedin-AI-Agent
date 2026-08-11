from pathlib import Path

import pytest
from PIL import Image

from linkedin_ai_agent.models import DraftPost
from linkedin_ai_agent.validators import validate_draft, validate_visual
from tests.test_ranking import config


def test_validate_draft_rejects_hype(tmp_path: Path):
    draft = DraftPost(
        topic="AI",
        category="tools",
        body="This revolutionary update is " + "useful. " * 40,
        hashtags=["#AI"],
        primary_source_url="https://example.com/primary",
        supporting_source_urls=["https://example.com/support"],
        claims=["claim"],
        visual_style="insight_card",
        visual_prompt="prompt",
        alt_text="alt",
    )
    report = validate_draft(draft, config(tmp_path))
    assert not report.passed
    assert any("hype" in reason for reason in report.reasons)


def test_validate_visual_requires_square(tmp_path: Path):
    path = tmp_path / "image.png"
    Image.new("RGB", (1200, 1200), "white").save(path)
    visual = validate_visual(path, "A concise alt text.")
    assert visual.width == 1200
    assert visual.height == 1200


def test_validate_visual_accepts_landscape_only_when_allowed(tmp_path: Path):
    path = tmp_path / "landscape.png"
    Image.new("RGB", (1600, 900), "white").save(path)

    with pytest.raises(ValueError, match="square"):
        validate_visual(path, "A concise alt text.")

    visual = validate_visual(path, "A concise alt text.", allow_landscape=True)
    assert visual.width == 1600
    assert visual.height == 900


def test_validate_visual_rejects_small_landscape(tmp_path: Path):
    path = tmp_path / "small-landscape.png"
    Image.new("RGB", (800, 450), "white").save(path)

    with pytest.raises(ValueError, match="too small"):
        validate_visual(path, "A concise alt text.", allow_landscape=True)


def test_validate_draft_rejects_ai_slop_patterns(tmp_path: Path):
    draft = DraftPost(
        topic="AI",
        category="tools",
        body="Here is the thing: this robust tool is a game changer for teams.",
        hashtags=["#AI"],
        primary_source_url="https://example.com/primary",
        supporting_source_urls=["https://example.com/support"],
        claims=["claim"],
        visual_style="insight_card",
        visual_prompt="prompt",
        alt_text="alt",
    )
    report = validate_draft(draft, config(tmp_path))
    assert not report.passed
    assert any("AI-style" in reason for reason in report.reasons)
