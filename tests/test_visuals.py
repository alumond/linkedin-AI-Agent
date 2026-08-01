from pathlib import Path

from PIL import Image

from linkedin_ai_agent.models import DraftPost
from linkedin_ai_agent.visuals import render_insight_card
from tests.test_ranking import config


def test_insight_card_is_visual_not_blank_text_page(tmp_path: Path):
    draft = DraftPost(
        topic="Multimodal AI moves into production workflows",
        category="AI releases",
        body="Body",
        hashtags=["#AI"],
        primary_source_url="https://example.com",
        supporting_source_urls=["https://example.com/2"],
        claims=["claim"],
        visual_style="insight_card",
        visual_prompt="",
        alt_text="Alt",
    )
    path = render_insight_card(draft, config(tmp_path), tmp_path / "card.png")
    with Image.open(path) as image:
        colors = image.convert("RGB").getcolors(maxcolors=1_000_000)
    assert colors is not None
    assert len(colors) > 20
