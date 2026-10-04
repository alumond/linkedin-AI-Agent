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


@pytest.mark.parametrize("detail", [
    "The system prompt defines the response.",
    "See `app.py` for the implementation.",
    "The details are in api/telegram.py.",
])
def test_validate_draft_rejects_code_walkthrough_details(tmp_path: Path, detail: str):
    cfg = config(tmp_path)
    cfg.min_post_chars, cfg.max_post_chars = 100, 1500
    body = f"""Health for All organises a symptom description into urgency, immediate actions, and warning signs.

{detail} Readers can use the public demonstration to inspect how the guidance is presented without treating the output as a diagnosis.

The interface keeps its limitation visible and directs serious symptoms toward timely clinical evaluation.

The project remains a demonstration and does not establish clinical accuracy or safety."""
    draft = DraftPost(
        topic="Health for All", category="portfolio", body=body,
        hashtags=["#DataProducts"], primary_source_url="https://github.com/example/health",
        supporting_source_urls=["https://github.com/example/health/blob/main/README.md"],
        claims=["claim"], visual_style="project_screenshot", visual_prompt="Authentic app screen",
        alt_text="Health for All app screen.", target_audience="analytics managers",
    )
    report = validate_draft(draft, cfg)
    assert any("file-path" in reason for reason in report.reasons)


def test_validate_draft_allows_public_app_urls(tmp_path: Path):
    cfg = config(tmp_path)
    cfg.min_post_chars, cfg.max_post_chars = 100, 1500
    body = """Health for All organises a symptom description into urgency, immediate actions, and warning signs.

The public demonstration shows the response format without claiming that the answer is clinically correct.

Try the app: https://health-example.streamlit.app/

The project remains a demonstration and does not replace clinical care."""
    draft = DraftPost(
        topic="Health for All", category="portfolio", body=body,
        hashtags=["#DataProducts"], primary_source_url="https://github.com/example/health",
        supporting_source_urls=["https://github.com/example/health/blob/main/README.md"],
        claims=["claim"], visual_style="project_screenshot", visual_prompt="Authentic app screen",
        alt_text="Health for All app screen.", target_audience="analytics managers",
    )
    assert not any("file-path" in reason for reason in validate_draft(draft, cfg).reasons)


def test_validate_draft_enforces_engagement_recovery_rules(tmp_path: Path):
    cfg = config(tmp_path)
    cfg.min_post_chars, cfg.max_post_chars = 500, 1600
    cfg.min_hashtags, cfg.max_hashtags = 3, 5
    cfg.audience_segments = ["analytics managers"]
    body = """A monthly revenue review needs a clear comparison period and an agreed owner.

The first block explains the decision, the evidence behind it, and the operating constraint that could change the interpretation. It gives the reader enough context to understand why the measure belongs in a management review.

Why this matters

The next block explains how the manager should compare the current result with the baseline, confirm the source data, and record any exception before assigning an action. This keeps the recommendation tied to evidence and avoids an unsupported claim.

The final review note should record the threshold, action owner, due date, and evidence required to close the issue."""
    draft = DraftPost(
        topic="Monthly revenue review", category="analytics", body=body,
        hashtags=["#Analytics", "#Revenue"], primary_source_url="https://example.com/primary",
        supporting_source_urls=["https://example.com/support"], claims=["claim"],
        visual_style="insight_card", visual_prompt="prompt", alt_text="alt",
        target_audience="analytics managers", invites_response=False,
    )
    reasons = validate_draft(draft, cfg).reasons
    assert any("at least 3" in reason for reason in reasons)
    assert any("stock section label" in reason for reason in reasons)


def test_scheduled_response_post_requires_one_specific_final_question(tmp_path: Path):
    cfg = config(tmp_path)
    cfg.min_post_chars, cfg.max_post_chars = 400, 1600
    body = """A retention review needs one cohort definition before the team compares results.

The analysis should hold the observation period constant and separate repeat purchases from newly acquired customers. That gives the manager a fair comparison and keeps campaign activity from masking customer quality.

The review should also check refunds, delivery delays, and support demand before crediting the campaign for healthier growth. Those measures can change the recommendation even when order volume rises.

A useful decision note would state the cohort, comparison window, commercial objective, and owner. It would also record the evidence that could reverse the recommendation and the date when the team will review the result again. That creates a clear trail from the observed behaviour to the budget decision.

Which supporting measure would you require before increasing the campaign budget?"""
    draft = DraftPost(
        topic="Retention review", category="analytics", body=body, hashtags=["#Analytics"],
        primary_source_url="https://example.com/primary", supporting_source_urls=["https://example.com/support"],
        claims=["claim"], visual_style="insight_card", visual_prompt="prompt", alt_text="alt",
        target_audience="growth leaders", invites_response=True,
    )
    assert validate_draft(draft, cfg).passed
