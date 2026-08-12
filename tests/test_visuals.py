from pathlib import Path

from PIL import Image

from linkedin_ai_agent.agent import FALLBACK_TOPIC_LIBRARY
from linkedin_ai_agent.models import DraftPost
from linkedin_ai_agent.visuals import render_diagram, render_insight_card
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


def test_all_curated_weekday_visual_styles_render(tmp_path: Path):
    cfg = config(tmp_path)
    seen_styles = set()
    for index, topic in enumerate(FALLBACK_TOPIC_LIBRARY):
        visual_style = str(topic["visual_style"])
        if visual_style in seen_styles:
            continue
        seen_styles.add(visual_style)
        base_style, _, variant = visual_style.partition(":")
        draft = DraftPost(
            topic=str(topic["topic"]),
            category=str(topic["category"]),
            body="Body",
            hashtags=list(topic["hashtags"]),
            primary_source_url="https://example.com",
            supporting_source_urls=["https://example.com/2"],
            claims=[str(topic["summary"])],
            visual_style=visual_style,
            visual_prompt=str(topic["visual_prompt"]),
            alt_text="Alt",
        )
        output_path = tmp_path / f"style-{index}.png"
        if base_style == "diagram":
            path = render_diagram(draft, cfg, output_path, variant=variant or "default")
        else:
            path = render_insight_card(draft, cfg, output_path, variant=variant or "default")

        with Image.open(path) as image:
            assert image.size == (1200, 1200)
            colors = image.convert("RGB").getcolors(maxcolors=1_000_000)
        assert colors is not None
        assert len(colors) > 20
