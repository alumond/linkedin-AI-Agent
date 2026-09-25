from __future__ import annotations

import json
import re
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
