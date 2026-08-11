from pathlib import Path

from linkedin_ai_agent.config import AgentConfig
from linkedin_ai_agent.history import PublicationHistory
from linkedin_ai_agent.models import EvidenceSource, TrendCandidate
from linkedin_ai_agent.ranking import has_required_sources, rank_candidates


def config(tmp_path: Path) -> AgentConfig:
    return AgentConfig(
        audience="everyone",
        editorial_topics=["AI"],
        excluded_subjects=[],
        voice="practical",
        min_post_chars=10,
        max_post_chars=500,
        brand_name="Brand",
        brand_colors=["#111827", "#2563EB", "#F8FAFC"],
        typography="Inter",
        timezone="Africa/Lagos",
        schedule_cron_utc="0 8 * * 1-5",
        source_allowlist=[],
        preferred_source_domains=["arxiv.org"],
        blocked_domains=["linkedin.com"],
        min_total_score=0.7,
        min_sources=2,
        min_primary_sources=1,
        min_independent_sources=1,
        duplicate_lookback_days=45,
        text_model="gemini-3.6-flash",
        image_model="gemini-3.1-flash-image",
        allow_ai_illustrations=False,
        visual_provider="local",
        linkedin_owner_urn="urn:li:person:test",
        linkedin_version="202605",
        reports_dir=tmp_path / "reports",
        assets_dir=tmp_path / "assets",
        state_dir=tmp_path / "state",
    )


def trend(topic: str, score: float = 0.9) -> TrendCandidate:
    return TrendCandidate(
        topic=topic,
        category="research",
        summary="summary",
        recency_score=score,
        relevance_score=score,
        evidence_score=score,
        practical_value_score=score,
        novelty_score=score,
        sources=[
            EvidenceSource(title="Paper", url="https://arxiv.org/abs/123", source_type="primary"),
            EvidenceSource(title="News", url="https://example.com/story", source_type="independent"),
        ],
    )


def test_has_required_sources_accepts_primary_and_independent(tmp_path):
    assert has_required_sources(trend("AI topic"), config(tmp_path))


def test_rank_candidates_filters_low_score_and_duplicates(tmp_path):
    cfg = config(tmp_path)
    history = PublicationHistory(cfg.state_dir)
    history.append({"created_at": "2026-07-31T08:00:00Z", "topic": "Already Covered"})
    ranked = rank_candidates([trend("Already Covered"), trend("Fresh Topic"), trend("Weak", 0.1)], cfg, history)
    assert [item.topic for item in ranked] == ["Fresh Topic"]
