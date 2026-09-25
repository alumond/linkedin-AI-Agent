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
