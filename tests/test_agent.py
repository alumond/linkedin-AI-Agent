import json
from pathlib import Path

import pytest
from PIL import Image

from linkedin_ai_agent.agent import LinkedInAIAgent, dedupe_urls, normalize_alt_text
from linkedin_ai_agent.models import DraftPost, VisualAsset
from tests.test_ranking import config, trend


class FakeGemini:
    def research(self, cfg, recent_topics):
        return [trend("Fresh Gemini Trend")], [{"title": "Citation", "url": "https://example.com"}]

    def generate_post(self, cfg, candidate):
        return DraftPost(
            topic=candidate.topic,
            category=candidate.category,
            body="A grounded Data and AI update for professionals. " * 6,
            hashtags=["#AI", "#Data"],
            primary_source_url="https://arxiv.org/abs/123",
            supporting_source_urls=["https://example.com/story"],
            claims=["The trend is supported by a primary source and independent reporting."],
            visual_style="insight_card",
            visual_prompt="Create a professional source-grounded card.",
            alt_text="A square source-grounded Data and AI insight card.",
        )


def test_dry_run_does_not_publish(tmp_path: Path):
    agent = LinkedInAIAgent(config(tmp_path), gemini=FakeGemini())
    result = agent.run(dry_run=True)
    assert result.status == "dry_run_ok"
    assert result.post_urn is None
    assert result.report_path


def test_normalize_alt_text_falls_back_and_truncates():
    assert normalize_alt_text("", "AI topic", "insight_card").startswith("Square LinkedIn insight card")
    assert len(normalize_alt_text("x" * 400, "AI topic", "diagram")) == 300


def test_dedupe_urls_preserves_order():
    assert dedupe_urls(["https://a.com", " https://a.com ", "https://b.com"]) == ["https://a.com", "https://b.com"]


def test_research_with_diagnostics_reports_rejections(tmp_path: Path):
    class WeakGemini:
        def research(self, cfg, recent_topics):
            weak = trend("Weak trend")
            weak.sources = []
            return [weak], []

    agent = LinkedInAIAgent(config(tmp_path), gemini=WeakGemini())
    ranked, citations, diagnostics = agent.research_with_diagnostics()
    assert ranked == []
    assert citations == []
    assert diagnostics[0]["topic"] == "Weak trend"
    assert diagnostics[0]["reasons"]


def test_publish_staged_uses_exact_reviewed_draft_once(tmp_path: Path):
    class FakeLinkedIn:
        def __init__(self):
            self.published_body = None

        def upload_image(self, visual):
            return "urn:li:image:test"

        def publish_post(self, draft, image_urn):
            self.published_body = draft.body
            return "urn:li:share:test"

    cfg = config(tmp_path)
    fake_linkedin = FakeLinkedIn()
    agent = LinkedInAIAgent(cfg, linkedin=fake_linkedin)
    image_path = tmp_path / "approved.png"
    Image.new("RGB", (1200, 1200), "white").save(image_path)
    draft = DraftPost(
        topic="A specific AI release",
        category="AI releases",
        body="The vendor released a specific feature on Tuesday. Teams can now test it against their existing workflow before deciding whether it is useful.",
        hashtags=["#AI"],
        primary_source_url="https://example.com/primary",
        supporting_source_urls=["https://example.org/report"],
        claims=["The feature was released Tuesday."],
        visual_style="insight_card",
        visual_prompt="",
        alt_text="Editorial illustration about a new AI release.",
    )
    visual = VisualAsset(str(image_path), "image/png", 1200, 1200, draft.alt_text)
    staged_path = agent.stage_preview(draft, visual, [])

    result = agent.publish_staged()

    assert result.status == "published"
    assert fake_linkedin.published_body == draft.body
    assert json.loads(staged_path.read_text(encoding="utf-8"))["status"] == "published"
    with pytest.raises(RuntimeError, match="cannot be published again"):
        agent.publish_staged()
