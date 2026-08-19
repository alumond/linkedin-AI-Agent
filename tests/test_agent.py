import json
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image

from linkedin_ai_agent.agent import FEATURED_DASHBOARD_IMAGE, FEATURED_DASHBOARD_LINK, LinkedInAIAgent, dedupe_urls, normalize_alt_text
from linkedin_ai_agent.config import load_config
from linkedin_ai_agent.models import DraftPost, VisualAsset
from linkedin_ai_agent.validators import validate_draft
from tests.test_ranking import config, trend


class FakeGemini:
    def research(self, cfg, recent_topics):
        return [trend("Fresh Gemini Trend")], [{"title": "Citation", "url": "https://example.com"}]

    def generate_post(self, cfg, candidate):
        body = """A practical AI update should connect source, risk, and action.

Fresh Gemini Trend

The source matters because teams need to know whether a change affects reporting quality, operating decisions, or the way analysts explain uncertainty. A post with only a headline does not help anyone decide what to do next.

The useful move is to name the decision path clearly: what changed, why it matters, what should be checked, and what action is safe to take now. That keeps the content grounded instead of turning it into another generic technology update.

Project context:
https://example.com/primary

Discussion prompts:
1) What would you check before turning this into a workflow change?
2) Which metric would prove the update is useful?"""
        return DraftPost(
            topic=candidate.topic,
            category=candidate.category,
            body=body,
            hashtags=["#AI", "#Data"],
            primary_source_url="https://arxiv.org/abs/123",
            supporting_source_urls=["https://example.com/story"],
            claims=["The trend is supported by a primary source and independent reporting."],
            visual_style="insight_card",
            visual_prompt="Create a professional source-grounded card.",
            alt_text="A square source-grounded Data and AI insight card.",
        )


def test_dry_run_does_not_publish(tmp_path: Path):
    cfg = config(tmp_path)
    cfg.min_post_chars = 2000
    cfg.max_post_chars = 3000
    cfg.allow_ai_illustrations = False
    agent = LinkedInAIAgent(cfg, gemini=FakeGemini())
    result = agent.run(dry_run=True)
    assert result.status == "dry_run_ok"
    assert result.post_urn is None
    assert result.report_path
    report = json.loads(Path(result.report_path).read_text(encoding="utf-8"))
    assert report["gemini_grounding_citations"] == []
    assert "Discussion prompts:" not in report["draft"]["body"]
    assert len(report["draft"]["body"]) >= cfg.min_post_chars


def test_codex_manual_missing_generated_asset_skips_before_dry_run(tmp_path: Path):
    cfg = config(tmp_path)
    cfg.min_post_chars = 2000
    cfg.max_post_chars = 3000
    cfg.visual_provider = "codex_manual"
    agent = LinkedInAIAgent(cfg)

    result = agent.run(dry_run=True)

    assert result.status == "skipped"
    assert "A Codex-generated topic-specific image is required" in result.skipped_reason


def test_codex_manual_missing_topic_asset_rejects_generated_library_image(tmp_path: Path):
    cfg = config(tmp_path)
    cfg.min_post_chars = 2000
    cfg.max_post_chars = 3000
    cfg.visual_provider = "codex_manual"
    cfg.assets_dir.mkdir(parents=True)
    Image.new("RGB", (1200, 1200), "white").save(cfg.assets_dir / "codex_generated_tradeoff.png")
    agent = LinkedInAIAgent(cfg)

    result = agent.run(dry_run=True)

    assert result.status == "skipped"
    assert "topic-specific image" in result.skipped_reason


def test_live_codex_manual_missing_asset_does_not_publish_with_api_key(tmp_path: Path, monkeypatch):
    class FakeLinkedIn:
        def upload_image(self, visual):
            raise AssertionError("missing Codex image must block upload")

        def publish_post(self, draft, image_urn):
            raise AssertionError("missing Codex image must block publish")

    cfg = config(tmp_path)
    cfg.min_post_chars = 2000
    cfg.max_post_chars = 3000
    cfg.visual_provider = "codex_manual"
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    agent = LinkedInAIAgent(cfg, linkedin=FakeLinkedIn())

    result = agent.run(dry_run=False)

    assert result.status == "skipped"
    assert "A Codex-generated topic-specific image is required" in result.skipped_reason


def test_codex_manual_topic_asset_is_used_and_fingerprinted(tmp_path: Path):
    class FakeLinkedIn:
        def upload_image(self, visual):
            return "urn:li:image:test"

        def publish_post(self, draft, image_urn):
            return "urn:li:share:test"

    cfg = config(tmp_path)
    cfg.min_post_chars = 2000
    cfg.max_post_chars = 3000
    cfg.visual_provider = "codex_manual"
    agent = LinkedInAIAgent(cfg, linkedin=FakeLinkedIn())
    for candidate in agent._fallback_trend_candidates():
        draft = agent._fallback_draft(candidate)
        asset = agent._codex_manual_visual_path(draft)
        asset.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (1200, 1200), "white").save(asset)

    result = agent.run(dry_run=False)

    assert result.status == "published"
    report = json.loads(Path(result.report_path).read_text(encoding="utf-8"))
    assert report["visual_generation"]["provider"] == "codex_manual_topic_asset"
    history = json.loads((cfg.state_dir / "publication_history.json").read_text(encoding="utf-8"))
    assert history[-1]["visual_path"] == report["visual_generation"]["asset"]
    assert len(history[-1]["visual_sha256"]) == 64


def test_recent_codex_manual_visual_reuse_is_blocked(tmp_path: Path):
    cfg = config(tmp_path)
    cfg.min_post_chars = 2000
    cfg.max_post_chars = 3000
    cfg.visual_provider = "codex_manual"
    agent = LinkedInAIAgent(cfg)
    cfg.state_dir.mkdir(parents=True, exist_ok=True)
    cfg.state_dir.joinpath("weekday_rotation_state.json").write_text(
        json.dumps(
            {
                "weekday_index": 1,
                "weekday_last_active_day": datetime.now().date().isoformat(),
                "weekday_special_day": 2,
            }
        ),
        encoding="utf-8",
    )
    draft = agent._fallback_draft(agent._pick_fallback_candidate(agent._fallback_trend_candidates()))
    asset = agent._codex_manual_visual_path(draft)
    asset.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1200, 1200), "white").save(asset)
    cfg.state_dir.joinpath("publication_history.json").write_text(
        json.dumps([{"created_at": "2026-08-12T00:00:00Z", "visual_path": str(asset)}]),
        encoding="utf-8",
    )

    result = agent.run(dry_run=True)

    assert result.status == "skipped"
    assert "already used recently" in result.skipped_reason


def test_all_curated_fallback_drafts_pass_production_length_gate(tmp_path: Path):
    cfg = load_config("config/agent.yaml")
    cfg.reports_dir = tmp_path / "reports"
    cfg.assets_dir = tmp_path / "assets"
    cfg.state_dir = tmp_path / "state"
    agent = LinkedInAIAgent(cfg)

    failures = []
    for candidate in agent._fallback_trend_candidates():
        draft = agent._fallback_draft(candidate)
        report = validate_draft(draft, cfg)
        if not report.passed:
            failures.append((candidate.topic, report.reasons))

    assert failures == []


def test_curated_fallback_copy_uses_linkedin_native_section_labels(tmp_path: Path):
    cfg = config(tmp_path)
    agent = LinkedInAIAgent(cfg)
    draft = agent._fallback_draft(agent._fallback_trend_candidates()[0])

    assert "WHY THIS MATTERS:" not in draft.body
    assert "THE COMMON MISTAKE:" not in draft.body
    assert "MY PRACTICAL RULE:" not in draft.body
    assert "Why this matters\n\n" in draft.body


def test_curated_fallback_visual_prompt_uses_readable_infographic_standard(tmp_path: Path):
    cfg = config(tmp_path)
    agent = LinkedInAIAgent(cfg)
    draft = agent._fallback_draft(agent._fallback_trend_candidates()[0])

    assert "LinkedIn infographic" in draft.visual_prompt
    assert "short readable captions" in draft.visual_prompt
    assert "Use square or landscape format" in draft.visual_prompt
    assert "no readable words" not in draft.visual_prompt.lower()
    assert "no text overlay" not in draft.visual_prompt.lower()


def test_manual_generate_still_revises_invalid_gemini_draft(tmp_path: Path):
    class RevisingGemini(FakeGemini):
        def __init__(self):
            self.revision_count = 0

        def generate_post(self, cfg, candidate):
            draft = super().generate_post(cfg, candidate)
            draft.body = "x" * (cfg.max_post_chars + 1)
            return draft

        def revise_post(self, cfg, candidate, draft, validation_reasons):
            self.revision_count += 1
            assert "Post length" in validation_reasons[0]
            return super().generate_post(cfg, candidate)

    gemini = RevisingGemini()
    cfg = config(tmp_path)
    cfg.min_post_chars = 700
    cfg.max_post_chars = 1300
    agent = LinkedInAIAgent(cfg, gemini=gemini)

    draft, visual = agent.generate(trend("Fresh Gemini Trend"))

    assert draft.topic == "Fresh Gemini Trend"
    assert visual.width == 1200
    assert gemini.revision_count == 1


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
    cfg.min_post_chars = 700
    cfg.max_post_chars = 1300
    fake_linkedin = FakeLinkedIn()
    agent = LinkedInAIAgent(cfg, linkedin=fake_linkedin)
    image_path = tmp_path / "approved.png"
    Image.new("RGB", (1200, 1200), "white").save(image_path)
    body = """A staged post should publish the exact reviewed draft.

A specific AI release

The point of staging is to prevent the live publisher from changing the wording or visual after a human has approved it. That matters when the post carries a portfolio claim, a source link, or a business judgment that must stay consistent.

This example keeps the wording complete enough for LinkedIn: it has context, analysis, a source path, and prompts. If the image changes after preview, the publish step should fail instead of posting a different asset.

Project context:
https://example.com/primary

Discussion prompts:
1) What should always be locked before publishing a post?
2) Which mistake is worse: wrong text or wrong image?"""
    draft = DraftPost(
        topic="A specific AI release",
        category="AI releases",
        body=body,
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


def test_featured_dashboard_dry_run_uses_fixed_post_without_gemini(tmp_path: Path):
    class ExplodingGemini:
        def research(self, cfg, recent_topics):
            raise AssertionError("Featured dashboard post must not research with Gemini.")

        def generate_post(self, cfg, candidate):
            raise AssertionError("Featured dashboard post must not generate with Gemini.")

    cfg = config(tmp_path)
    cfg.min_post_chars = 700
    cfg.max_post_chars = 1300
    cfg.assets_dir.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1600, 900), "white").save(cfg.assets_dir / FEATURED_DASHBOARD_IMAGE)

    agent = LinkedInAIAgent(cfg, gemini=ExplodingGemini())
    result = agent.publish_featured_dashboard(dry_run=True)

    assert result.status == "dry_run_ok"
    assert result.post_urn is None
    assert result.report_path
    report = json.loads(Path(result.report_path).read_text(encoding="utf-8"))
    body = report["draft"]["body"]
    assert "2,160 synthetic retail operations rows" in body
    assert "Analyst note:" in body
    assert FEATURED_DASHBOARD_LINK in body
    assert report["visual"]["width"] == 1600
    assert report["visual"]["height"] == 900
