import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from PIL import Image

from linkedin_ai_agent.agent import FEATURED_DASHBOARD_IMAGE, FEATURED_DASHBOARD_LINK, LinkedInAIAgent, dedupe_urls, normalize_alt_text, normalize_draft
from linkedin_ai_agent.codex_visuals import draft_sha256
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


def record_test_review(agent, draft, asset):
    normalize_draft(draft)
    record = {
        "provider": "codex_imagegen", "review_status": "passed",
        "topic": draft.topic, "draft_sha256": draft_sha256(draft),
        "asset_sha256": agent._visual_sha256(asset),
        "prompt": "Test fixture only", "review_notes": "Test fixture only",
        "reviewed_at": datetime.now().isoformat(), "alt_text": draft.alt_text,
    }
    asset.with_suffix(".json").write_text(json.dumps(record))


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

    assert result.status == "pending_image"
    assert "A Codex-generated topic-specific image is required" in result.pending_reason


def test_codex_manual_missing_topic_asset_rejects_generated_library_image(tmp_path: Path):
    cfg = config(tmp_path)
    cfg.min_post_chars = 2000
    cfg.max_post_chars = 3000
    cfg.visual_provider = "codex_manual"
    cfg.assets_dir.mkdir(parents=True)
    Image.new("RGB", (1200, 1200), "white").save(cfg.assets_dir / "codex_generated_tradeoff.png")
    agent = LinkedInAIAgent(cfg)

    result = agent.run(dry_run=True)

    assert result.status == "pending_image"
    assert "topic-specific image" in result.pending_reason


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

    assert result.status == "pending_image"
    assert "A Codex-generated topic-specific image is required" in result.pending_reason


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
        record_test_review(agent, draft, asset)

    result = agent.run(dry_run=False)

    assert result.status == "published"
    report = json.loads(Path(result.report_path).read_text(encoding="utf-8"))
    assert report["visual_generation"]["provider"] == "codex_imagegen"
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
    record_test_review(agent, draft, asset)
    cfg.state_dir.joinpath("publication_history.json").write_text(
        json.dumps([{"created_at": datetime.now().isoformat() + "Z", "visual_path": str(asset)}]),
        encoding="utf-8",
    )

    result = agent.run(dry_run=True)

    assert result.status == "pending_image"
    assert "already used recently" in result.pending_reason


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


@pytest.mark.parametrize('change', ['missing_review', 'wrong_provider', 'changed_image', 'changed_post', 'failed_review'])
def test_codex_gate_rejects_unreviewed_or_mismatched_assets(tmp_path, change):
    cfg = config(tmp_path)
    cfg.visual_provider = 'codex_manual'
    agent = LinkedInAIAgent(cfg)
    draft = FakeGemini().generate_post(cfg, trend('Fresh Gemini Trend'))
    asset = agent._codex_manual_visual_path(draft)
    asset.parent.mkdir(parents=True, exist_ok=True)
    Image.new('RGB', (1200, 1200), 'white').save(asset)
    record_test_review(agent, draft, asset)
    record_path = asset.with_suffix('.json')
    record = json.loads(record_path.read_text())
    if change == 'missing_review':
        record_path.unlink()
    elif change == 'changed_image':
        Image.new('RGB', (1200, 1200), 'blue').save(asset)
    elif change == 'changed_post':
        draft.body += '\nA different recommendation.'
    else:
        record['provider' if change == 'wrong_provider' else 'review_status'] = 'local' if change == 'wrong_provider' else 'failed'
        record_path.write_text(json.dumps(record))
    with pytest.raises(RuntimeError):
        agent._render_visual(draft)
    assert list((cfg.assets_dir / 'briefs').glob('*.json'))


def test_generate_obeys_codex_provider_without_local_fallback(tmp_path, monkeypatch):
    cfg = config(tmp_path)
    cfg.visual_provider = 'codex_manual'
    cfg.min_post_chars, cfg.max_post_chars = 700, 1300
    agent = LinkedInAIAgent(cfg, gemini=FakeGemini())
    def forbidden(*args, **kwargs):
        raise AssertionError('Local rendering must never be used in Codex mode')
    monkeypatch.setattr('linkedin_ai_agent.agent.render_insight_card', forbidden)
    with pytest.raises(RuntimeError, match='Codex-generated'):
        agent.generate(trend('Fresh Gemini Trend'))
    draft = agent.generate_draft(trend('Fresh Gemini Trend'))
    asset = agent._codex_manual_visual_path(draft)
    Image.new('RGB', (1600, 900), 'white').save(asset)
    record_test_review(agent, draft, asset)
    generated, visual = agent.generate(trend('Fresh Gemini Trend'))
    assert visual.path == str(asset)
    assert (visual.width, visual.height) == (1600, 900)
    agent.stage_preview(generated, visual, [])
    asset.with_suffix('.json').unlink()
    with pytest.raises(RuntimeError, match='review record'):
        agent.publish_staged()


def test_staging_cannot_bypass_codex_gate(tmp_path):
    cfg = config(tmp_path)
    cfg.visual_provider = 'codex_manual'
    agent = LinkedInAIAgent(cfg)
    draft = FakeGemini().generate_post(cfg, trend('Fresh Gemini Trend'))
    asset = tmp_path / 'local.png'
    Image.new('RGB', (1200, 1200), 'white').save(asset)
    with pytest.raises(RuntimeError, match='reviewed Codex asset'):
        agent.stage_preview(draft, VisualAsset(str(asset), 'image/png', 1200, 1200, 'Local'), [])
    assert not (cfg.state_dir / 'pending_post.json').exists()


def test_pending_image_keeps_same_post_until_image_arrives(tmp_path, monkeypatch):
    class Publisher:
        def __init__(self):
            self.bodies = []
        def upload_image(self, visual):
            return 'urn:li:image:test'
        def publish_post(self, draft, image_urn):
            self.bodies.append(draft.body)
            return 'urn:li:share:test'
    cfg = config(tmp_path)
    cfg.visual_provider = 'codex_manual'
    cfg.min_post_chars, cfg.max_post_chars = 2000, 3000
    publisher = Publisher()
    agent = LinkedInAIAgent(cfg, linkedin=publisher)
    first = agent.run(dry_run=False)
    assert first.status == 'pending_image'
    pending_path = cfg.state_dir / 'pending_image_post.json'
    pending = json.loads(pending_path.read_text())
    def forbidden(*args, **kwargs):
        raise AssertionError('A pending post must not be replaced by another topic')
    monkeypatch.setattr(agent, '_pick_fallback_candidate', forbidden)
    assert agent.run(dry_run=False).status == 'pending_image'
    from linkedin_ai_agent.models import draft_from_dict
    draft = draft_from_dict(pending['draft'])
    asset = agent._codex_manual_visual_path(draft)
    Image.new('RGB', (1200, 1200), 'white').save(asset)
    record_test_review(agent, draft, asset)
    assert agent.run(dry_run=True).status == 'dry_run_ok'
    assert pending_path.exists()
    assert publisher.bodies == []
    assert agent.run(dry_run=False).status == 'published'
    assert publisher.bodies == [draft.body]
    assert not pending_path.exists()


def test_dry_run_missing_image_does_not_queue_live_post(tmp_path):
    cfg = config(tmp_path)
    cfg.visual_provider = 'codex_manual'
    cfg.min_post_chars, cfg.max_post_chars = 2000, 3000
    assert LinkedInAIAgent(cfg).run(dry_run=True).status == 'pending_image'
    assert not (cfg.state_dir / 'pending_image_post.json').exists()


def test_replacement_at_same_path_can_use_a_fresh_image(tmp_path):
    cfg = config(tmp_path)
    agent = LinkedInAIAgent(cfg)
    asset = tmp_path / 'replacement.png'
    Image.new('RGB', (1200, 1200), 'white').save(asset)
    old_hash = agent._visual_sha256(asset)
    agent.history.append({'created_at': datetime.now().isoformat() + 'Z',
                          'visual_path': str(asset), 'visual_sha256': old_hash})
    with pytest.raises(RuntimeError, match='already used'):
        agent._ensure_visual_not_reused(asset, old_hash)
    Image.new('RGB', (1200, 1200), 'blue').save(asset)
    agent._ensure_visual_not_reused(asset, agent._visual_sha256(asset))


def test_exhausted_library_never_returns_published_topics(tmp_path):
    agent = LinkedInAIAgent(config(tmp_path))
    for candidate in agent._fallback_trend_candidates():
        agent.history.append({"created_at": datetime.now(timezone.utc).isoformat(), "topic": candidate.topic})
    assert agent._fallback_trend_candidates() == []
    result = agent.run(dry_run=False)
    assert result.status == "skipped"
    assert "No curated weekday topic" in result.skipped_reason


def test_recycled_body_is_blocked_before_image_or_upload(tmp_path, monkeypatch):
    cfg = config(tmp_path)
    cfg.min_post_chars, cfg.max_post_chars = 2000, 3000
    agent = LinkedInAIAgent(cfg)
    candidates = agent._fallback_trend_candidates()
    candidate = next(c for c in candidates if c.category == 'data cleaning')
    draft = agent._fallback_draft(candidate)
    agent.history.append({"created_at": datetime.now(timezone.utc).isoformat(),
                          "topic": "A different headline", "body": draft.body})
    monkeypatch.setattr(agent, '_pick_fallback_candidate', lambda candidates: candidate)
    def forbidden(*args, **kwargs):
        raise AssertionError('Recycled text must be stopped before visual generation')
    monkeypatch.setattr(agent, '_render_visual', forbidden)
    result = agent.run(dry_run=False)
    assert result.status == 'skipped'
    assert 'repeats substantial wording' in result.skipped_reason


def test_configured_image_preferences_reach_draft(tmp_path):
    cfg = load_config('config/agent.yaml')
    cfg.state_dir = tmp_path / 'state'
    agent = LinkedInAIAgent(cfg)
    draft = agent._fallback_draft(agent._fallback_trend_candidates()[0])
    assert cfg.visual_direction in draft.visual_prompt
    assert 'sketches and hand-drawn illustrations' in draft.visual_prompt
    assert 'model drawings and wireframes' in draft.visual_prompt
