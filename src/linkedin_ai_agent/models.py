from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class EvidenceSource:
    title: str
    url: str
    publisher: str = ""
    source_type: str = "independent"
    published_at: str | None = None
    claim_supported: str = ""
    quality_score: float = 0.0


@dataclass
class TrendCandidate:
    topic: str
    category: str
    summary: str
    recency_score: float
    relevance_score: float
    evidence_score: float
    practical_value_score: float
    novelty_score: float
    sources: list[EvidenceSource] = field(default_factory=list)

    @property
    def total_score(self) -> float:
        return round(
            self.recency_score * 0.22
            + self.relevance_score * 0.22
            + self.evidence_score * 0.24
            + self.practical_value_score * 0.18
            + self.novelty_score * 0.14,
            4,
        )


@dataclass
class DraftPost:
    topic: str
    category: str
    body: str
    hashtags: list[str]
    primary_source_url: str
    supporting_source_urls: list[str]
    claims: list[str]
    visual_style: str
    visual_prompt: str
    alt_text: str


@dataclass
class VisualAsset:
    path: str
    mime_type: str
    width: int
    height: int
    alt_text: str
    linkedin_image_urn: str | None = None


@dataclass
class SafetyReport:
    passed: bool
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class PublishResult:
    status: str
    dry_run: bool
    topic: str | None = None
    post_urn: str | None = None
    image_urn: str | None = None
    skipped_reason: str | None = None
    report_path: str | None = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat(timespec="seconds") + "Z")


def to_dict(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, list):
        return [to_dict(item) for item in value]
    if isinstance(value, dict):
        return {key: to_dict(item) for key, item in value.items()}
    return value


def source_from_dict(data: dict[str, Any]) -> EvidenceSource:
    return EvidenceSource(
        title=str(data.get("title", "")),
        url=str(data.get("url", "")),
        publisher=str(data.get("publisher", "")),
        source_type=str(data.get("source_type", "independent")),
        published_at=data.get("published_at"),
        claim_supported=str(data.get("claim_supported", "")),
        quality_score=float(data.get("quality_score", 0.0)),
    )


def trend_from_dict(data: dict[str, Any]) -> TrendCandidate:
    return TrendCandidate(
        topic=str(data.get("topic", "")),
        category=str(data.get("category", "explainer")),
        summary=str(data.get("summary", "")),
        recency_score=float(data.get("recency_score", 0.0)),
        relevance_score=float(data.get("relevance_score", 0.0)),
        evidence_score=float(data.get("evidence_score", 0.0)),
        practical_value_score=float(data.get("practical_value_score", 0.0)),
        novelty_score=float(data.get("novelty_score", 0.0)),
        sources=[source_from_dict(item) for item in data.get("sources", [])],
    )


def draft_from_dict(data: dict[str, Any]) -> DraftPost:
    return DraftPost(
        topic=str(data.get("topic", "")),
        category=str(data.get("category", "explainer")),
        body=str(data.get("body", "")),
        hashtags=[str(item) for item in data.get("hashtags", [])],
        primary_source_url=str(data.get("primary_source_url", "")),
        supporting_source_urls=[str(item) for item in data.get("supporting_source_urls", [])],
        claims=[str(item) for item in data.get("claims", [])],
        visual_style=str(data.get("visual_style", "insight_card")),
        visual_prompt=str(data.get("visual_prompt", "")),
        alt_text=str(data.get("alt_text", "")),
    )


def visual_from_dict(data: dict[str, Any]) -> VisualAsset:
    return VisualAsset(
        path=str(data.get("path", "")),
        mime_type=str(data.get("mime_type", "application/octet-stream")),
        width=int(data.get("width", 0)),
        height=int(data.get("height", 0)),
        alt_text=str(data.get("alt_text", "")),
        linkedin_image_urn=data.get("linkedin_image_urn"),
    )
