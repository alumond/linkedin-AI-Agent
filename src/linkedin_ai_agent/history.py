from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class PublicationHistory:
    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir
        self.path = state_dir / "publication_history.json"
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return json.loads(self.path.read_text(encoding="utf-8"))

    def recent_topics(self, lookback_days: int) -> list[str]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        topics: list[str] = []
        for item in self.load():
            created_at = str(item.get("created_at", ""))
            try:
                parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            except ValueError:
                continue
            if parsed >= cutoff and item.get("topic"):
                topics.append(str(item["topic"]).lower())
        return topics

    def is_duplicate(self, topic: str, lookback_days: int) -> bool:
        normalized = " ".join(topic.lower().split())
        return normalized in {" ".join(item.split()) for item in self.recent_topics(lookback_days)}

    def append(self, record: dict[str, Any]) -> None:
        items = self.load()
        items.append(record)
        self.path.write_text(json.dumps(items, indent=2, sort_keys=True), encoding="utf-8")
