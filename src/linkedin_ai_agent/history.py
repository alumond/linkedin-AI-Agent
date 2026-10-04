from __future__ import annotations

import json
import re
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from difflib import SequenceMatcher
from zoneinfo import ZoneInfo


def history_cutoff(lookback_days: int) -> datetime:
    return (datetime.now(timezone.utc) - timedelta(days=lookback_days)
            if lookback_days else datetime.min.replace(tzinfo=timezone.utc))


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


class PublicationHistory:
    def __init__(self, state_dir: Path, reports_dir: Path | None = None) -> None:
        self.state_dir = state_dir
        self.reports_dir = reports_dir or state_dir.parent / "reports"
        self.path = state_dir / "publication_history.json"
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text(encoding="utf-8"))

    def recent_topics(self, lookback_days: int) -> list[str]:
        cutoff = history_cutoff(lookback_days)
        topics: list[str] = []
        for item in self.load():
            created_at = str(item.get("created_at", ""))
            try:
                parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except ValueError:
                continue
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            if parsed >= cutoff and item.get("topic"):
                topics.append(str(item["topic"]).lower())
        return topics

    def is_duplicate(self, topic: str, lookback_days: int) -> bool:
        normalize = lambda value: " ".join(re.findall(r"\w+", value.casefold()))
        normalized = normalize(topic)
        return any(normalized == normalize(item) or
                   SequenceMatcher(None, normalized, normalize(item)).ratio() >= 0.9
                   for item in self.recent_topics(lookback_days))

    def published_today(self, timezone_name: str) -> dict[str, Any] | None:
        zone = ZoneInfo(timezone_name)
        today = datetime.now(zone).date()
        for item in reversed(self.load()):
            if not item.get("post_urn"):
                continue
            created = datetime.fromisoformat(item["created_at"].replace("Z", "+00:00"))
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if created.astimezone(zone).date() == today:
                return item
        return None

    def similar_body_topic(self, body: str, lookback_days: int) -> str | None:
        """Catch recycled copy even when its title or opening has changed.

        Older records store the copy in the audit report; new records retain it
        directly. Five-word overlap measures shared phrasing, not shared subject.
        """
        def shingles(text: str) -> set[tuple[str, ...]]:
            words = re.findall(r"\w+", text.casefold())
            return {tuple(words[i:i + 5]) for i in range(len(words) - 4)}

        current = shingles(body)
        if not current:
            return None
        cutoff = history_cutoff(lookback_days)
        for item in self.load():
            try:
                created = datetime.fromisoformat(str(item.get("created_at", "")).replace("Z", "+00:00"))
            except ValueError:
                continue
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if created < cutoff:
                continue
            previous = item.get("body", "")
            if not previous and item.get("report_path"):
                report_path = self.reports_dir / Path(item["report_path"]).name
                # Missing historical evidence must not silently weaken this gate.
                report = json.loads(report_path.read_text(encoding="utf-8"))
                previous = report.get("draft", {}).get("body", "")
            old = shingles(previous)
            if old and len(current & old) / min(len(current), len(old)) >= 0.8:
                return str(item.get("topic") or "previously published post")
        return None

    def similar_boundary(self, body: str, lookback_days: int) -> tuple[str, str] | None:
        """Return the earlier topic and boundary when an opening or close feels recycled."""
        def boundaries(text: str) -> tuple[str, str]:
            blocks = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
            return (blocks[0] if blocks else "", blocks[-1] if blocks else "")

        def normalized(text: str) -> str:
            return " ".join(re.findall(r"\w+", text.casefold()))

        opening, closing = boundaries(body)
        current = {"opening": normalized(opening), "closing": normalized(closing)}
        cutoff = history_cutoff(lookback_days)
        for item in reversed(self.load()):
            try:
                created = datetime.fromisoformat(str(item.get("created_at", "")).replace("Z", "+00:00"))
            except ValueError:
                continue
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if created < cutoff:
                continue
            previous = str(item.get("body") or "")
            if not previous and item.get("report_path"):
                report_path = self.reports_dir / Path(item["report_path"]).name
                report = json.loads(report_path.read_text(encoding="utf-8"))
                previous = str(report.get("draft", {}).get("body", ""))
            old_opening, old_closing = boundaries(previous)
            old = {"opening": normalized(old_opening), "closing": normalized(old_closing)}
            for boundary in ("opening", "closing"):
                new_text, old_text = current[boundary], old[boundary]
                if min(len(new_text), len(old_text)) < 24:
                    continue
                if new_text == old_text or SequenceMatcher(None, new_text, old_text).ratio() >= 0.86:
                    return str(item.get("topic") or "previously published post"), boundary
        return None

    def recent_visual_fingerprints(self, lookback_days: int) -> set[str]:
        cutoff = history_cutoff(lookback_days)
        fingerprints: set[str] = set()
        for item in self.load():
            created_at = str(item.get("created_at", ""))
            try:
                parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except ValueError:
                continue
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            if parsed < cutoff:
                continue
            # A fresh generation may replace a file at the same topic path.
            # Legacy records without a hash still fall back to the path guard.
            for key in (("visual_sha256",) if item.get("visual_sha256") else ("visual_path",)):
                value = item.get(key)
                if value:
                    fingerprints.add(str(value))
        return fingerprints

    def append(self, record: dict[str, Any]) -> None:
        items = self.load()
        items.append(record)
        atomic_json(self.path, items)

    def record_engagement(self, post_urn: str, metrics: dict[str, int], measured_at: str) -> dict[str, Any]:
        allowed = ("impressions", "reactions", "comments", "reposts", "profile_views", "follows", "clicks")
        cleaned = {}
        for key in allowed:
            raw = metrics.get(key, 0)
            if isinstance(raw, bool):
                raise ValueError("Engagement metrics must be whole numbers.")
            try:
                numeric = float(raw)
            except (TypeError, ValueError) as exc:
                raise ValueError("Engagement metrics must be whole numbers.") from exc
            if not numeric.is_integer():
                raise ValueError("Engagement metrics must be whole numbers.")
            cleaned[key] = int(numeric)
        if any(value < 0 for value in cleaned.values()):
            raise ValueError("Engagement metrics cannot be negative.")
        if cleaned["impressions"] <= 0:
            raise ValueError("Impressions must be greater than zero.")
        cleaned["measured_at"] = measured_at
        cleaned["interaction_rate_percent"] = round(
            100 * (cleaned["reactions"] + cleaned["comments"] + cleaned["reposts"]) / cleaned["impressions"], 2
        )
        items = self.load()
        for item in items:
            if item.get("post_urn") == post_urn:
                item["engagement"] = cleaned
                atomic_json(self.path, items)
                return item
        raise ValueError("The selected published post was not found in publication history.")

    def engagement_scorecard(self, strategy_version: str, window_posts: int,
                             baseline_impressions: int, target_median_impressions: int,
                             target_posts_with_reactions: int, target_posts_with_comments: int) -> dict[str, Any]:
        eligible = [item for item in self.load()
                    if item.get("strategy_version") == strategy_version and item.get("engagement")]
        measured = eligible[-max(1, window_posts):]
        impressions = [int(item["engagement"]["impressions"]) for item in measured]
        median_impressions = round(statistics.median(impressions), 1) if impressions else None
        reaction_posts = sum(int(item["engagement"].get("reactions", 0)) > 0 for item in measured)
        comment_posts = sum(int(item["engagement"].get("comments", 0)) > 0 for item in measured)
        return {
            "strategy_version": strategy_version,
            "measured_posts": len(measured),
            "window_posts": window_posts,
            "median_impressions": median_impressions,
            "baseline_impressions": baseline_impressions,
            "target_median_impressions": target_median_impressions,
            "posts_with_reactions": reaction_posts,
            "target_posts_with_reactions": target_posts_with_reactions,
            "posts_with_comments": comment_posts,
            "target_posts_with_comments": target_posts_with_comments,
        }
