from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config import AgentConfig
from .gemini_client import GeminiClient
from .history import PublicationHistory
from .linkedin_client import LinkedInClient
from .models import DraftPost, PublishResult, TrendCandidate, VisualAsset, draft_from_dict, to_dict, visual_from_dict
from .ranking import candidate_rejection_reasons, rank_candidates
from .reports import write_report
from .validators import validate_draft, validate_trend, validate_visual
from .visuals import render_diagram, render_insight_card


class LinkedInAIAgent:
    def __init__(
        self,
        config: AgentConfig,
        gemini: GeminiClient | None = None,
        linkedin: LinkedInClient | None = None,
    ) -> None:
        self.config = config
        self.history = PublicationHistory(config.state_dir)
        self.gemini = gemini
        self.linkedin = linkedin

    def research(self) -> tuple[list[TrendCandidate], list[dict[str, Any]]]:
        gemini = self.gemini or GeminiClient()
        recent = self.history.recent_topics(self.config.duplicate_lookback_days)
        candidates, citations = gemini.research(self.config, recent)
        return rank_candidates(candidates, self.config, self.history), citations

    def research_with_diagnostics(self) -> tuple[list[TrendCandidate], list[dict[str, Any]], list[dict[str, Any]]]:
        gemini = self.gemini or GeminiClient()
        recent = self.history.recent_topics(self.config.duplicate_lookback_days)
        candidates, citations = gemini.research(self.config, recent)
        ranked = rank_candidates(candidates, self.config, self.history)
        diagnostics = [
            {
                "topic": candidate.topic,
                "score": candidate.total_score,
                "reasons": candidate_rejection_reasons(candidate, self.config, self.history),
            }
            for candidate in candidates
            if candidate not in ranked
        ]
        return ranked, citations, diagnostics

    def generate(self, candidate: TrendCandidate) -> tuple[DraftPost, VisualAsset]:
        gemini = self.gemini or GeminiClient()
        draft = gemini.generate_post(self.config, candidate)
        normalize_draft(draft)
        draft_report = validate_draft(draft, self.config)
        if not draft_report.passed:
            draft = gemini.revise_post(self.config, candidate, draft, draft_report.reasons)
            normalize_draft(draft)
            draft_report = validate_draft(draft, self.config)
            if not draft_report.passed:
                raise ValueError("Draft revision failed validation: " + "; ".join(draft_report.reasons))
        asset_path = self._visual_path(draft)
        if draft.visual_style == "diagram":
            render_diagram(draft, self.config, asset_path)
        elif draft.visual_style == "illustration" and self.config.allow_ai_illustrations:
            gemini.generate_illustration(self.config, draft, asset_path)
        else:
            render_insight_card(draft, self.config, asset_path)
        visual = validate_visual(asset_path, draft.alt_text)
        return draft, visual

    def run(self, dry_run: bool) -> PublishResult:
        try:
            candidates, citations = self.research()
        except Exception as exc:
            return self._skip(str(exc), citations=[])
        if not candidates:
            return self._skip("No trend passed ranking and evidence gates.", citations=citations)
        candidate = candidates[0]
        trend_report = validate_trend(candidate, self.config, self.history)
        if not trend_report.passed:
            return self._skip("; ".join(trend_report.reasons), candidate=candidate, citations=citations)
        try:
            draft, visual = self.generate(candidate)
            draft_report = validate_draft(draft, self.config)
            if not draft_report.passed:
                return self._skip("; ".join(draft_report.reasons), candidate=candidate, draft=draft, citations=citations)
            image_urn = None
            post_urn = None
            if not dry_run:
                linkedin = self.linkedin or LinkedInClient.from_env(self.config)
                image_urn = linkedin.upload_image(visual)
                visual.linkedin_image_urn = image_urn
                post_urn = linkedin.publish_post(draft, image_urn)
            result = PublishResult(
                status="dry_run_ok" if dry_run else "published",
                dry_run=dry_run,
                topic=draft.topic,
                post_urn=post_urn,
                image_urn=image_urn,
            )
            payload = {
                "status": result.status,
                "dry_run": dry_run,
                "selected_topic": candidate.topic,
                "trend": candidate,
                "draft": draft,
                "visual": visual,
                "gemini_grounding_citations": citations,
                "safety": {"trend": trend_report, "draft": draft_report},
                "publish": result,
            }
            report_path = write_report(self.config.reports_dir, payload)
            result.report_path = str(report_path)
            if not dry_run:
                self.history.append(
                    {
                        "created_at": result.created_at,
                        "topic": draft.topic,
                        "category": draft.category,
                        "post_urn": post_urn,
                        "image_urn": image_urn,
                        "primary_source_url": draft.primary_source_url,
                        "report_path": str(report_path),
                    }
                )
            return result
        except Exception as exc:
            return self._skip(str(exc), candidate=candidate, citations=citations)

    def stage_preview(self, draft: DraftPost, visual: VisualAsset, citations: list[dict[str, Any]]) -> Path:
        """Save the exact reviewed text and image so live publishing cannot regenerate them."""
        image_path = Path(visual.path)
        payload = {
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "draft": to_dict(draft),
            "visual": to_dict(visual),
            "citations": citations,
            "image_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
        }
        self.config.state_dir.mkdir(parents=True, exist_ok=True)
        path = self.config.state_dir / "pending_post.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path

    def publish_staged(self) -> PublishResult:
        """Publish only the immutable preview currently staged for human approval."""
        path = self.config.state_dir / "pending_post.json"
        if not path.exists():
            raise RuntimeError("No staged preview exists. Run the preview command first.")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("status") != "pending":
            raise RuntimeError(f"The staged preview is {payload.get('status', 'invalid')} and cannot be published again.")

        draft = draft_from_dict(payload.get("draft", {}))
        visual = visual_from_dict(payload.get("visual", {}))
        draft_report = validate_draft(draft, self.config)
        if not draft_report.passed:
            raise RuntimeError("Staged post failed the writing gate: " + "; ".join(draft_report.reasons))
        checked_visual = validate_visual(Path(visual.path), visual.alt_text)
        actual_hash = hashlib.sha256(Path(visual.path).read_bytes()).hexdigest()
        if actual_hash != payload.get("image_sha256"):
            raise RuntimeError("The staged image changed after preview. Generate and review a new preview.")

        linkedin = self.linkedin or LinkedInClient.from_env(self.config)
        payload["status"] = "publishing"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        try:
            image_urn = linkedin.upload_image(checked_visual)
            post_urn = linkedin.publish_post(draft, image_urn)
        except Exception:
            payload["status"] = "failed"
            path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            raise

        result = PublishResult(
            status="published",
            dry_run=False,
            topic=draft.topic,
            post_urn=post_urn,
            image_urn=image_urn,
        )
        payload.update({"status": "published", "post_urn": post_urn, "image_urn": image_urn, "published_at": result.created_at})
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        report_path = write_report(
            self.config.reports_dir,
            {
                "status": "published",
                "selected_topic": draft.topic,
                "draft": draft,
                "visual": checked_visual,
                "gemini_grounding_citations": payload.get("citations", []),
                "safety": {"draft": draft_report},
                "publish": result,
            },
        )
        result.report_path = str(report_path)
        self.history.append(
            {
                "created_at": result.created_at,
                "topic": draft.topic,
                "category": draft.category,
                "post_urn": post_urn,
                "image_urn": image_urn,
                "primary_source_url": draft.primary_source_url,
                "report_path": str(report_path),
            }
        )
        return result

    def token_status(self) -> dict[str, Any]:
        path = self.config.state_dir / "linkedin_token_metadata.json"
        if not path.exists():
            env_expires_at = os.environ.get("LINKEDIN_TOKEN_EXPIRES_AT")
            if not env_expires_at:
                return {"status": "missing", "message": "No token metadata found."}
            data = {"expires_at": env_expires_at}
        else:
            import json

            data = json.loads(path.read_text(encoding="utf-8"))
        expires_at = datetime.fromisoformat(str(data["expires_at"]).replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        days_remaining = (expires_at - now).days
        return {
            "status": "expired" if expires_at <= now else "expiring_soon" if days_remaining <= 7 else "valid",
            "expires_at": data["expires_at"],
            "days_remaining": days_remaining,
        }

    def _skip(
        self,
        reason: str,
        candidate: TrendCandidate | None = None,
        draft: DraftPost | None = None,
        citations: list[dict[str, Any]] | None = None,
    ) -> PublishResult:
        result = PublishResult(status="skipped", dry_run=True, topic=candidate.topic if candidate else None, skipped_reason=reason)
        report_path = write_report(
            self.config.reports_dir,
            {
                "status": "skipped",
                "reason": reason,
                "topic": candidate.topic if candidate else None,
                "trend": candidate,
                "draft": draft,
                "gemini_grounding_citations": citations or [],
                "publish": result,
            },
        )
        result.report_path = str(report_path)
        return result

    def _visual_path(self, draft: DraftPost) -> Path:
        stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in draft.topic).strip("-")[:50] or "visual"
        return self.config.assets_dir / f"{stamp}-{slug}.png"


def token_metadata(expires_in: int) -> dict[str, str]:
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    return {"expires_at": expires_at.isoformat(timespec="seconds").replace("+00:00", "Z")}


def normalize_draft(draft: DraftPost) -> None:
    draft.hashtags = [tag if tag.startswith("#") else f"#{tag}" for tag in draft.hashtags[:3] if tag.strip()]
    draft.supporting_source_urls = dedupe_urls(draft.supporting_source_urls)[:3]
    draft.alt_text = normalize_alt_text(draft.alt_text, draft.topic, draft.visual_style)


def normalize_alt_text(alt_text: str, topic: str, visual_style: str) -> str:
    cleaned = " ".join((alt_text or "").split())
    if not cleaned:
        style = "diagram" if visual_style == "diagram" else "insight card"
        cleaned = f"Square LinkedIn {style} summarizing: {topic}."
    if len(cleaned) > 300:
        cleaned = cleaned[:297].rstrip() + "..."
    return cleaned


def dedupe_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for url in urls:
        cleaned = url.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result
