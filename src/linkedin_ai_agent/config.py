from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class AgentConfig:
    audience: str
    editorial_topics: list[str]
    excluded_subjects: list[str]
    voice: str
    min_post_chars: int
    max_post_chars: int
    brand_name: str
    brand_colors: list[str]
    typography: str
    timezone: str
    schedule_cron_utc: str
    source_allowlist: list[str]
    preferred_source_domains: list[str]
    blocked_domains: list[str]
    min_total_score: float
    min_sources: int
    min_primary_sources: int
    min_independent_sources: int
    duplicate_lookback_days: int
    text_model: str
    image_model: str
    allow_ai_illustrations: bool
    linkedin_owner_urn: str
    linkedin_version: str
    reports_dir: Path
    assets_dir: Path
    state_dir: Path


def load_config(path: str | Path) -> AgentConfig:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    post_length = data.get("post_length", {})
    brand = data.get("brand", {})
    thresholds = data.get("thresholds", {})
    models = data.get("models", {})
    visuals = data.get("visuals", {})
    linkedin = data.get("linkedin", {})
    dirs = data.get("directories", {})
    return AgentConfig(
        audience=str(data.get("audience", "Broad professionals")),
        editorial_topics=list(data.get("editorial_topics", [])),
        excluded_subjects=list(data.get("excluded_subjects", [])),
        voice=str(data.get("voice", "insightful, human, practical")),
        min_post_chars=int(post_length.get("min_chars", 700)),
        max_post_chars=int(post_length.get("max_chars", 1300)),
        brand_name=str(brand.get("name", "Data & AI Brief")),
        brand_colors=list(brand.get("colors", ["#111827", "#2563EB", "#F8FAFC"])),
        typography=str(brand.get("typography", "Inter")),
        timezone=str(data.get("timezone", "Africa/Lagos")),
        schedule_cron_utc=str(data.get("schedule_cron_utc", "0 8 * * 1-5")),
        source_allowlist=list(data.get("source_allowlist", [])),
        preferred_source_domains=list(data.get("preferred_source_domains", [])),
        blocked_domains=list(data.get("blocked_domains", [])),
        min_total_score=float(thresholds.get("min_total_score", 0.72)),
        min_sources=int(thresholds.get("min_sources", 2)),
        min_primary_sources=int(thresholds.get("min_primary_sources", 1)),
        min_independent_sources=int(thresholds.get("min_independent_sources", 1)),
        duplicate_lookback_days=int(thresholds.get("duplicate_lookback_days", 45)),
        text_model=str(models.get("text", "gemini-2.5-flash")),
        image_model=str(models.get("image", "gemini-3.1-flash-image")),
        allow_ai_illustrations=bool(visuals.get("allow_ai_illustrations", False)),
        linkedin_owner_urn=str(linkedin.get("owner_urn", "")),
        linkedin_version=str(linkedin.get("version", "202605")),
        reports_dir=Path(dirs.get("reports", "reports")),
        assets_dir=Path(dirs.get("assets", "assets")),
        state_dir=Path(dirs.get("state", ".state")),
    )


def public_config(config: AgentConfig) -> dict[str, Any]:
    data = asdict(config)
    for key in ("reports_dir", "assets_dir", "state_dir"):
        data[key] = str(data[key])
    return data
