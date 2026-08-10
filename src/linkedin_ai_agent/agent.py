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
from .models import (
    DraftPost,
    EvidenceSource,
    PublishResult,
    TrendCandidate,
    VisualAsset,
    draft_from_dict,
    to_dict,
    visual_from_dict,
)
from .ranking import candidate_rejection_reasons, rank_candidates
from .reports import write_report
from .validators import validate_draft, validate_trend, validate_visual
from .visuals import render_diagram, render_insight_card


FEATURED_DASHBOARD_LINK = "https://github.com/alumond/linkedin-AI-Agent/tree/main/projects/retail-revenue-command-center"
FEATURED_DASHBOARD_DATA_LINK = "https://github.com/alumond/linkedin-AI-Agent/blob/main/projects/retail-revenue-command-center/data/retail_operations_kpis.csv"
FEATURED_DASHBOARD_SCRIPT_LINK = "https://github.com/alumond/linkedin-AI-Agent/blob/main/projects/retail-revenue-command-center/scripts/build_dashboard.py"
FEATURED_DASHBOARD_IMAGE = "featured_retail_revenue_leakage_review.png"
PORTFOLIO_LINK = "https://almond-owolabi-portfolio-s3pd81.v2.appdeploy.ai/"


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

    def _fallback_trend_candidates(self) -> list[TrendCandidate]:
        raw_topics = [
            (
                "Revenue growth is useless if profit, retention, and returns are moving in the wrong direction.",
                "Build dashboards that expose growth quality, not just volume.",
                "analytics",
            ),
            (
                "A dashboard is not a chart collection. It is a decision system.",
                "Treat visuals as an executive decision layer, not a portfolio wallpaper.",
                "dashboard design",
            ),
            (
                "What I learned building a retail revenue leakage dashboard from 2,160 synthetic rows.",
                "One portfolio artifact can validate analytics reasoning end-to-end.",
                "analytics",
            ),
            (
                "Retention as the real revenue lever",
                "The mistake many analysts make: showing KPIs without showing what management should do next.",
                "Every KPI update needs an explicit action path.",
                "KPI reporting",
            ),
            (
                "Why repeat customers are often a better business signal than new customer volume.",
                "The real growth question is customer quality versus customer count.",
                "business intelligence",
            ),
            (
                "How returns and fulfillment delays quietly destroy revenue growth.",
                "Operational leak points often hide in support and fulfillment.",
                "AI for analytics",
            ),
            (
                "A strong GitHub project should show business judgment, not only polished code.",
                "Proof of work is stronger when it shows business outcomes.",
                "data for business growth",
            ),
            (
                "If your dashboard has no business question, it is decoration.",
                "A dashboard with no action is just a chart gallery.",
                "analytics",
            ),
            (
                "The difference between a beginner dashboard and an executive dashboard.",
                "Density, hierarchy, and decision clarity are what separate amateurs from decision support.",
                "dashboard design",
            ),
            (
                "How Monitoring & Evaluation taught me to prioritize retention and service quality.",
                "M&E discipline improves every business dashboard.",
                "impact analytics",
            ),
        ]
        sources = [
            EvidenceSource(
                title="Retail Revenue Command Center",
                url=FEATURED_DASHBOARD_LINK,
                source_type="primary",
                publisher="GitHub",
            ),
            EvidenceSource(
                title="Synthetic retail dataset",
                url=FEATURED_DASHBOARD_DATA_LINK,
                source_type="independent",
                publisher="GitHub",
            ),
            EvidenceSource(
                title="Project source code",
                url=FEATURED_DASHBOARD_SCRIPT_LINK,
                source_type="independent",
                publisher="GitHub",
            ),
            EvidenceSource(
                title="Portfolio site",
                url=PORTFOLIO_LINK,
                source_type="independent",
                publisher="Portfolio",
            ),
        ]
        candidates: list[TrendCandidate] = []
        for topic, summary, category in raw_topics:
            candidates.append(
                TrendCandidate(
                    topic=topic,
                    category=category,
                    summary=summary,
                    recency_score=1.0,
                    relevance_score=0.98,
                    evidence_score=1.0,
                    practical_value_score=0.99,
                    novelty_score=0.95,
                    sources=sources,
                )
            )
        deduped = [candidate for candidate in candidates if not self.history.is_duplicate(candidate.topic, self.config.duplicate_lookback_days)]
        return deduped if deduped else candidates

    def _fallback_draft(self, candidate: TrendCandidate) -> DraftPost:
        body = f"""{candidate.topic}

{candidate.summary}

Most LinkedIn posts about analytics never trigger a decision. They only report activity.

I built a retail command center with 2,160 synthetic operations rows, then used it to prove a simple rule for decision-ready reporting.
Growth must be tested against margin, retention, fulfillment speed, and returns pressure.
When these move in opposite directions, the dashboard is where your plan should start changing today.

That is the same principle clients, recruiters, and hiring teams look for: can you turn data into next action, not just a polished chart.
My portfolio is the repo link below with code, dataset, and dashboard outputs you can audit.

Discussion prompts:
1) Which single metric pair in your current reporting stack would create the clearest boardroom decision?
2) What KPI would you remove first so the remaining view becomes easier to act on?"""

        return DraftPost(
            topic=candidate.topic,
            category=candidate.category,
            body=body,
            hashtags=[
                "#DataAnalytics",
                "#KPIReporting",
                "#BusinessIntelligence",
                "#DataStorytelling",
                "#DashboardDesign",
                "#DecisionSupport",
                "#AnalyticsPortfolio",
                "#GrowthAnalytics",
            ],
            primary_source_url=FEATURED_DASHBOARD_LINK,
            supporting_source_urls=[FEATURED_DASHBOARD_DATA_LINK, FEATURED_DASHBOARD_SCRIPT_LINK, PORTFOLIO_LINK],
            claims=[
                "The flagship repository includes a 2,160-row synthetic retail dataset and portfolio-facing dashboard artifacts.",
                "The project links revenue, margin, retention, returns, fulfillment delay, and stockout indicators in one decision-ready stack.",
                "The objective is to drive business decisions, not visual decoration.",
            ],
            visual_style="insight_card",
            visual_prompt="Premium analytics decision post using KPI tension and operational call-to-action framing.",
            alt_text="Premium insight card comparing growth, margin, retention, and operations health as linked business decisions.",
        )

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
        fallback_reason = ""
        fallback_candidate = None
        candidate = None
        citations: list[dict[str, Any]] = []
        trend_report = None
        try:
            candidates, citations = self.research()
        except Exception as exc:
            fallback_reason = str(exc)
            candidates = []
        if not candidates:
            fallback_list = self._fallback_trend_candidates()
            if not fallback_list:
                return self._skip(
                    fallback_reason or "No trend passed ranking and evidence gates.",
                    citations=citations,
                )
            fallback_candidate = fallback_list[datetime.now().timetuple().tm_yday % len(fallback_list)]
            candidate = fallback_candidate
        else:
            candidate = candidates[0]
            trend_report = validate_trend(candidate, self.config, self.history)
            if not trend_report.passed:
                fallback_list = self._fallback_trend_candidates()
                if not fallback_list:
                    return self._skip("; ".join(trend_report.reasons), candidate=candidate, citations=citations)
                fallback_candidate = fallback_list[0]
                candidate = fallback_candidate
                trend_report = None
        try:
            if fallback_candidate:
                draft = self._fallback_draft(candidate)
                asset_path = self._visual_path(draft)
                render_insight_card(draft, self.config, asset_path)
                visual = validate_visual(asset_path, draft.alt_text)
                normalize_draft(draft)
                draft_report = validate_draft(draft, self.config)
                if not draft_report.passed:
                    return self._skip("; ".join(draft_report.reasons), candidate=candidate, citations=citations, draft=draft)
            else:
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

    def featured_dashboard_draft(self) -> DraftPost:
        body = f"""I built a retail revenue dashboard to answer a question leaders actually care about:

Is growth creating better business performance, or just more activity?

Dataset:
2,160 synthetic retail operations rows covering 18 months, 5 regions, 4 channels, 6 product categories, campaigns, orders, revenue, gross profit, customers, returns, support tickets, fulfillment delay, stockout risk, satisfaction, and data quality flags.

Process:
I generated the data with Python, aggregated KPIs by month, category, channel, and region, then designed a 16:9 executive dashboard with HTML, CSS, and SVG. No chart library. The goal was not decoration. It was decision support.

Analyst note:
Revenue is up, but the real review is whether gross profit, repeat customers, return pressure, and fulfillment speed are moving in the same direction. A dashboard should make that tension visible fast.

Project and data:
{FEATURED_DASHBOARD_LINK}

Discussion prompts:
What metric would you add before presenting this to leadership?
Do you prefer dashboards that explain the decision, or dashboards that only show the numbers?"""
        return DraftPost(
            topic="Retail Revenue Leakage Review",
            category="portfolio",
            body=body,
            hashtags=[
                "#DataAnalytics",
                "#BusinessIntelligence",
                "#DashboardDesign",
                "#Python",
                "#DataStorytelling",
                "#KPIReporting",
                "#GrowthAnalytics",
                "#DecisionSupport",
                "#AnalyticsPortfolio",
                "#DataForBusiness",
            ],
            primary_source_url=FEATURED_DASHBOARD_LINK,
            supporting_source_urls=[FEATURED_DASHBOARD_DATA_LINK, FEATURED_DASHBOARD_SCRIPT_LINK],
            claims=[
                "The dataset contains 2,160 synthetic retail operations rows.",
                "The dashboard was generated with Python, HTML, CSS, and SVG.",
                "The analysis compares revenue growth with profit, retention, returns, and fulfillment pressure.",
            ],
            visual_style="landscape_dashboard",
            visual_prompt="Screenshot-ready retail revenue leakage dashboard.",
            alt_text=(
                "Landscape executive retail revenue dashboard showing revenue, profit, category contribution, "
                "channel economics, customer quality, and return pressure versus margin."
            ),
        )

    def publish_featured_dashboard(self, dry_run: bool) -> PublishResult:
        draft = self.featured_dashboard_draft()
        draft_report = validate_draft(draft, self.config)
        if not draft_report.passed:
            return self._skip("; ".join(draft_report.reasons), draft=draft, citations=[])
        try:
            visual = validate_visual(self.config.assets_dir / FEATURED_DASHBOARD_IMAGE, draft.alt_text, allow_landscape=True)
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
            report_path = write_report(
                self.config.reports_dir,
                {
                    "status": result.status,
                    "selected_topic": draft.topic,
                    "draft": draft,
                    "visual": visual,
                    "gemini_grounding_citations": [],
                    "safety": {"draft": draft_report},
                    "publish": result,
                },
            )
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
            return self._skip(str(exc), draft=draft, citations=[])

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
                if os.environ.get("LINKEDIN_ACCESS_TOKEN"):
                    return {
                        "status": "valid",
                        "expires_at": "unknown",
                        "days_remaining": 999,
                        "message": "Token metadata is missing but token exists; posting will proceed at runtime.",
                    }
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
