import json
from datetime import datetime, timedelta, timezone

from linkedin_ai_agent.history import PublicationHistory


COPY = """A retention review needs a clear customer cohort and a consistent observation window.
Separate repeat orders from new customer purchases before comparing performance.
Check refunds and late deliveries before crediting the campaign for healthier demand.
Give the operations owner a specific follow-up date and measure whether the change lasts."""


def test_changed_heading_does_not_hide_recycled_body(tmp_path):
    history = PublicationHistory(tmp_path / "state")
    history.append({"created_at": datetime.now(timezone.utc).isoformat(),
                    "topic": "Retention", "body": COPY})
    assert history.similar_body_topic("New opening and a different title.\n" + COPY, 180) == "Retention"
    assert history.similar_body_topic("Database migrations require verified backups, explicit version tracking, and a tested rollback procedure.", 180) is None


def test_legacy_audit_report_is_used_for_body_check(tmp_path):
    reports = tmp_path / "audit"
    reports.mkdir()
    (reports / "old.json").write_text(json.dumps({"draft": {"body": COPY}}))
    history = PublicationHistory(tmp_path / "state", reports)
    history.append({"created_at": datetime.now(timezone.utc).isoformat(),
                    "topic": "Previous post", "report_path": "reports/old.json"})
    assert history.similar_body_topic(COPY, 180) == "Previous post"


def test_body_check_respects_lookback(tmp_path):
    history = PublicationHistory(tmp_path / "state")
    history.append({"created_at": (datetime.now(timezone.utc) - timedelta(days=181)).isoformat(),
                    "topic": "Older post", "body": COPY})
    assert history.similar_body_topic(COPY, 180) is None


def test_repeated_opening_or_closing_is_detected_even_when_body_changes(tmp_path):
    history = PublicationHistory(tmp_path / "state")
    earlier = """A delayed KPI review can hide a problem until the next reporting cycle.

The earlier post contains a different analysis with its own evidence and recommendation.

Record the threshold, owner, action, and follow-up date in the same review note."""
    history.append({"created_at": datetime.now(timezone.utc).isoformat(),
                    "topic": "Earlier KPI review", "body": earlier})

    repeated_opening = """A delayed KPI review can hide a problem until the next reporting cycle.

This new post discusses a separate operating issue and uses different supporting detail.

Close with a distinct action for the new decision."""
    assert history.similar_boundary(repeated_opening, 180) == ("Earlier KPI review", "opening")

    repeated_closing = """A fresh opening about a different customer-retention decision.

This post uses separate evidence and a different analytical argument throughout.

Record the threshold, owner, action, and follow-up date in the same review note."""
    assert history.similar_boundary(repeated_closing, 180) == ("Earlier KPI review", "closing")


def test_engagement_scorecard_uses_only_new_strategy_posts(tmp_path):
    history = PublicationHistory(tmp_path / "state")
    history.append({"created_at": datetime.now(timezone.utc).isoformat(), "topic": "Legacy",
                    "post_urn": "legacy", "engagement": {"impressions": 900}})
    for index, impressions in enumerate((90, 150, 120), start=1):
        history.append({"created_at": datetime.now(timezone.utc).isoformat(), "topic": f"New {index}",
                        "post_urn": f"urn:{index}", "strategy_version": "engagement_recovery_v1"})
        history.record_engagement(f"urn:{index}", {
            "impressions": impressions, "reactions": index % 2, "comments": int(index == 3),
        }, datetime.now(timezone.utc).isoformat())
    score = history.engagement_scorecard("engagement_recovery_v1", 10, 80, 120, 5, 3)
    assert score["measured_posts"] == 3
    assert score["median_impressions"] == 120
    assert score["posts_with_reactions"] == 2
    assert score["posts_with_comments"] == 1
