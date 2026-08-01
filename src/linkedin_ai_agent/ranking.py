from __future__ import annotations

from urllib.parse import urlparse

from .config import AgentConfig
from .history import PublicationHistory
from .models import EvidenceSource, TrendCandidate


PRIMARY_HINTS = (
    "openai.com",
    "ai.google.dev",
    "deepmind.google",
    "microsoft.com",
    "anthropic.com",
    "meta.com",
    "nvidia.com",
    "arxiv.org",
    "nature.com",
    "science.org",
    "stanford.edu",
    "mit.edu",
)


def domain(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def classify_source(source: EvidenceSource) -> str:
    host = domain(source.url)
    if source.source_type in {"primary", "independent"}:
        return source.source_type
    if any(host.endswith(item) for item in PRIMARY_HINTS):
        return "primary"
    return "independent"


def source_allowed(source: EvidenceSource, config: AgentConfig) -> bool:
    host = domain(source.url)
    if any(host == blocked or host.endswith("." + blocked) for blocked in config.blocked_domains):
        return False
    if not config.source_allowlist:
        return True
    return any(host == allowed or host.endswith("." + allowed) for allowed in config.source_allowlist)


def has_required_sources(candidate: TrendCandidate, config: AgentConfig) -> bool:
    allowed_sources = [source for source in candidate.sources if source_allowed(source, config)]
    primary = [source for source in allowed_sources if classify_source(source) == "primary"]
    independent = [source for source in allowed_sources if classify_source(source) == "independent"]
    return (
        len(allowed_sources) >= config.min_sources
        and len(primary) >= config.min_primary_sources
        and len(independent) >= config.min_independent_sources
    )


def rank_candidates(
    candidates: list[TrendCandidate],
    config: AgentConfig,
    history: PublicationHistory,
) -> list[TrendCandidate]:
    filtered = [
        item
        for item in candidates
        if item.total_score >= config.min_total_score
        and has_required_sources(item, config)
        and not history.is_duplicate(item.topic, config.duplicate_lookback_days)
    ]
    return sorted(filtered, key=lambda item: item.total_score, reverse=True)


def candidate_rejection_reasons(
    candidate: TrendCandidate,
    config: AgentConfig,
    history: PublicationHistory,
) -> list[str]:
    reasons: list[str] = []
    if candidate.total_score < config.min_total_score:
        reasons.append(f"score {candidate.total_score:.2f} below {config.min_total_score:.2f}")
    if not has_required_sources(candidate, config):
        allowed_sources = [source for source in candidate.sources if source_allowed(source, config)]
        primary_count = sum(1 for source in allowed_sources if classify_source(source) == "primary")
        independent_count = sum(1 for source in allowed_sources if classify_source(source) == "independent")
        reasons.append(
            "source gate failed "
            f"({primary_count} primary, {independent_count} independent, {len(allowed_sources)} allowed)"
        )
    if history.is_duplicate(candidate.topic, config.duplicate_lookback_days):
        reasons.append("recent duplicate")
    return reasons
