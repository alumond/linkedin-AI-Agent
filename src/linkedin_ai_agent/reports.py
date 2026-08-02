from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import to_dict


def write_report(reports_dir: Path, payload: dict[str, Any]) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    topic = str(payload.get("topic") or payload.get("selected_topic") or "run")
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in topic).strip("-")[:60] or "run"
    path = reports_dir / f"{stamp}-{slug}.json"
    path.write_text(json.dumps(to_dict(payload), indent=2, sort_keys=True), encoding="utf-8")
    return path
