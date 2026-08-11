from __future__ import annotations

import re
from pathlib import Path

from PIL import Image

from .config import AgentConfig
from .history import PublicationHistory
from .models import DraftPost, SafetyReport, TrendCandidate, VisualAsset
from .ranking import has_required_sources


HYPE_TERMS = (
    "revolutionary",
    "game-changing",
    "mind-blowing",
    "guaranteed",
    "secret",
    "insane",
    "landscape is shifting dramatically",
    "what's particularly exciting",
    "are you ready",
    "powerful ai capabilities",
)
AI_SLOP_TERMS = (
    "delve",
    "foster",
    "leverage",
    "utilize",
    "facilitate",
    "empower",
    "streamline",
    "robust",
    "cutting-edge",
    "paradigm shift",
    "game changer",
    "this is huge",
    "this changes everything",
    "tapestry",
    "realm",
    "beacon",
    "multifaceted",
    "meticulous",
    "intricate",
    "paramount",
    "transformative",
    "elevate",
    "embark",
    "supercharge",
    "harness",
    "ever-evolving",
)
AI_SLOP_PATTERNS = (
    (r"\bhere(?:'|’)s the thing\b", "throat-clearing opener"),
    (r"\blet me be clear\b", "throat-clearing opener"),
    (r"\bwhat (?:most people|everyone) (?:miss|get wrong|misses)\b", "faux-insight setup"),
    (r"\bhere(?:'|’)s what nobody tells you\b", "faux-insight setup"),
    (r"\bwhat if i told you\b", "rhetorical setup"),
    (r"\b(?:experts agree|studies show|industry reports suggest|many argue)\b", "weasel attribution"),
    (r"\b(?:in conclusion|ultimately|overall),", "summary-recap ending"),
    (r"\bthis (?:is|isn't|is not) (?:just )?[^.!?]{1,80}[.!?]\s+(?:it(?:'s| is)|this is)\b", "binary contrast"),
)
UNSAFE_TERMS = ("defamatory", "hate speech", "adult explicit", "medical advice", "financial advice")


def validate_trend(candidate: TrendCandidate, config: AgentConfig, history: PublicationHistory) -> SafetyReport:
    reasons: list[str] = []
    if candidate.total_score < config.min_total_score:
        reasons.append(f"Trend score {candidate.total_score:.2f} is below threshold {config.min_total_score:.2f}.")
    if not has_required_sources(candidate, config):
        reasons.append("Trend does not have the required primary and independent source coverage.")
    if history.is_duplicate(candidate.topic, config.duplicate_lookback_days):
        reasons.append("Topic was covered recently.")
    return SafetyReport(passed=not reasons, reasons=reasons)


def validate_draft(draft: DraftPost, config: AgentConfig) -> SafetyReport:
    reasons: list[str] = []
    warnings: list[str] = []
    body = draft.body.strip()
    lowered = body.lower()
    is_curated_weekday = any("curated weekday opinion post" in claim.lower() for claim in draft.claims)
    words = re.findall(r"\b[\w']+\b", body)
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", body) if part.strip()]
    first_line = next((line.strip() for line in body.splitlines() if line.strip()), "")
    if not (config.min_post_chars <= len(body) <= config.max_post_chars):
        reasons.append(f"Post length {len(body)} is outside {config.min_post_chars}-{config.max_post_chars} chars.")
    if len(words) < 115:
        reasons.append("Post body is too thin; it must contain enough context to avoid a title-only LinkedIn post.")
    if len(paragraphs) < 5:
        reasons.append("Post needs at least five short paragraphs or blocks: hook, context, analysis, project/source, and prompts.")
    if first_line.lower().rstrip(".") == draft.topic.strip().lower().rstrip("."):
        reasons.append("Post opens with the topic as a standalone heading; use a human hook before the topic.")
    if not draft.primary_source_url and not is_curated_weekday:
        reasons.append("Primary source link is missing.")
    if not draft.supporting_source_urls and not is_curated_weekday:
        reasons.append("Supporting source link is missing.")
    if len(draft.hashtags) < 1:
        reasons.append("At least one hashtag is required.")
    if len(draft.hashtags) > 10:
        reasons.append("More than ten hashtags were provided.")
    if any(term in lowered for term in HYPE_TERMS):
        reasons.append("Post contains excessive hype or clickbait language.")
    found_slop = sorted({term for term in AI_SLOP_TERMS if re.search(rf"\b{re.escape(term)}\b", lowered)})
    if found_slop:
        reasons.append(f"Post contains generic AI-style wording: {', '.join(found_slop)}.")
    found_patterns = sorted({label for pattern, label in AI_SLOP_PATTERNS if re.search(pattern, lowered, re.IGNORECASE)})
    if found_patterns:
        reasons.append(f"Post contains artificial writing patterns: {', '.join(found_patterns)}.")
    if "—" in body:
        reasons.append("Post uses an em dash; use a clearer sentence break instead.")
    if re.search(r"[\U0001F300-\U0001FAFF]", body):
        reasons.append("Post contains decorative emoji.")
    if "significant percentage" in lowered or "many businesses" in lowered:
        reasons.append("Post contains vague quantified claims; use exact sourced numbers or remove the claim.")
    if any(term in lowered for term in UNSAFE_TERMS):
        reasons.append("Post contains unsafe content markers.")
    if re.search(r"\"[^\"]{20,}\"", body):
        warnings.append("Post appears to contain a quotation; verify it before live publishing.")
    if "i tested" in lowered or "i used this myself" in lowered:
        reasons.append("Post implies personal testing that may not have happened.")
    if "Discussion prompts:" not in body:
        reasons.append("Discussion prompts block is missing; add the required 'Discussion prompts:' section with two short prompts.")
    else:
        prompts = body.split("Discussion prompts:", 1)[1]
        prompt_markers = re.findall(r"(?m)^\s*(?:\d+\)|Q\d+:)", prompts)
        if len(prompt_markers) < 2:
            reasons.append("Discussion prompts block must contain at least two prompts marked as Q1/Q2 or numbered prompts.")
    return SafetyReport(passed=not reasons, reasons=reasons, warnings=warnings)


def validate_visual(path: Path, alt_text: str, allow_landscape: bool = False) -> VisualAsset:
    with Image.open(path) as image:
        width, height = image.size
        mime = Image.MIME.get(image.format, "application/octet-stream")
    if width == height:
        if width < 900:
            raise ValueError(f"Image is too small for LinkedIn. Got {width}px.")
    elif allow_landscape and abs((width / height) - (16 / 9)) <= 0.03:
        if width < 1200 or height < 675:
            raise ValueError(f"Landscape image is too small for LinkedIn. Got {width}x{height}.")
    else:
        expected = "square or approved 16:9 landscape" if allow_landscape else "square"
        raise ValueError(f"Image must be {expected}. Got {width}x{height}.")
    if not alt_text or len(alt_text) > 300:
        raise ValueError("Alt text must be present and 300 characters or fewer.")
    return VisualAsset(path=str(path), mime_type=mime, width=width, height=height, alt_text=alt_text)
