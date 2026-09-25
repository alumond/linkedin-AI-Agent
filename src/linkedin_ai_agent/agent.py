from __future__ import annotations

import hashlib
import inspect
import json
import os
import random
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config import AgentConfig
from .codex_visuals import draft_sha256, reviewed_visual, write_visual_brief, visual_signature
from .gemini_client import GeminiClient
from .history import PublicationHistory, atomic_json
from .linkedin_client import LinkedInClient
from .models import (
    DraftPost,
    EvidenceSource,
    PublishResult,
    TrendCandidate,
    VisualAsset,
    draft_from_dict,
    to_dict,
    trend_from_dict,
    visual_from_dict,
)
from .ranking import candidate_rejection_reasons, rank_candidates
from .reports import write_report
from .portfolio import GitHubProjects, excluded_material
from .validators import validate_draft, validate_trend, validate_visual
from .visuals import render_diagram, render_insight_card


FEATURED_DASHBOARD_LINK = "https://github.com/alumond/linkedin-AI-Agent/tree/main/projects/retail-revenue-command-center"
FEATURED_DASHBOARD_DATA_LINK = "https://github.com/alumond/linkedin-AI-Agent/blob/main/projects/retail-revenue-command-center/data/retail_operations_kpis.csv"
FEATURED_DASHBOARD_SCRIPT_LINK = "https://github.com/alumond/linkedin-AI-Agent/blob/main/projects/retail-revenue-command-center/scripts/build_dashboard.py"
FEATURED_DASHBOARD_IMAGE = "featured_retail_revenue_leakage_review.png"
PORTFOLIO_LINK = "https://almond-owolabi-portfolio-s3pd81.v2.appdeploy.ai/"


GITHUB_REPO_LINK = "https://github.com/alumond/linkedin-AI-Agent"


FALLBACK_TOPIC_LIBRARY = [
    {
        "topic": "Your spreadsheet is not messy. Your business process is messy.",
        "summary": "Messy data usually points to unclear ownership, inconsistent definitions, or a broken handoff.",
        "category": "data cleaning",
        "visual_style": "insight_card:editorial",
        "visual_prompt": "Show messy inputs becoming clear business ownership, not a decorative spreadsheet image.",
        "hashtags": ["#DataCleaning", "#DataAnalytics", "#BusinessProcess", "#Analytics", "#DataQuality", "#BusinessIntelligence"],
    },
    {
        "topic": "The fastest analyst is not the one who knows every tool. It is the one who asks better questions.",
        "summary": "Strong analysis starts with the business question before SQL, Python, Excel, or Power BI enters the room.",
        "category": "analytics mindset",
        "visual_style": "diagram:decision_grid",
        "visual_prompt": "Create a question-first decision map for analysts and business teams.",
        "hashtags": ["#DataAnalytics", "#AnalyticsMindset", "#BusinessIntelligence", "#DataSkills", "#DecisionMaking", "#CareerGrowth"],
    },
    {
        "topic": "Revenue dashboards should start with customer behavior, not total sales.",
        "summary": "Sales volume looks impressive until retention, repeat purchases, and refunds tell a different story.",
        "category": "growth analytics",
        "visual_style": "insight_card:stacked_grid",
        "visual_prompt": "Compare sales, retention, refunds, and repeat purchase signals in a business-friendly card.",
        "hashtags": ["#GrowthAnalytics", "#CustomerAnalytics", "#Revenue", "#Retention", "#DataAnalytics", "#BusinessGrowth"],
    },
    {
        "topic": "If your KPI has no owner, it is just a number with a nice font.",
        "summary": "A metric becomes useful when someone owns the threshold, action, and follow-up.",
        "category": "KPI reporting",
        "visual_style": "insight_card:focus_strip",
        "visual_prompt": "Show KPI ownership as signal, threshold, owner, action, and review.",
        "hashtags": ["#KPIReporting", "#BusinessIntelligence", "#DecisionSupport", "#Analytics", "#ManagementReporting", "#DataLeadership"],
    },
    {
        "topic": "Data cleaning is where business truth usually shows up.",
        "summary": "Duplicates, missing fields, and inconsistent labels often reveal the real operational problem.",
        "category": "data cleaning",
        "visual_style": "diagram:decision_grid",
        "visual_prompt": "Turn cleaning issues into business signals: duplicates, gaps, definitions, owners, next action.",
        "hashtags": ["#DataCleaning", "#DataQuality", "#DataAnalytics", "#Operations", "#BusinessIntelligence", "#AnalyticsPortfolio"],
    },
    {
        "topic": "A small dataset with a clear business question beats a huge dataset with no decision.",
        "summary": "The size of the dataset matters less than the decision it can support.",
        "category": "decision support",
        "visual_style": "insight_card:editorial",
        "visual_prompt": "Contrast small focused data with large unfocused data through a decision lens.",
        "hashtags": ["#DecisionSupport", "#DataAnalytics", "#BusinessAnalytics", "#DataStrategy", "#AnalyticsMindset", "#DataForBusiness"],
    },
    {
        "topic": "The best Power BI dashboard is the one that makes the next meeting shorter.",
        "summary": "A dashboard should reduce argument, not add more tabs for people to debate.",
        "category": "dashboard design",
        "visual_style": "insight_card:grid_strategic",
        "visual_prompt": "Show a meeting-shortening dashboard structure: signal, cause, owner, action.",
        "hashtags": ["#PowerBI", "#DashboardDesign", "#BusinessIntelligence", "#DataViz", "#DecisionMaking", "#KPIReporting"],
    },
    {
        "topic": "Founders do not need more charts. They need fewer blind spots.",
        "summary": "Business dashboards should expose risk, leakage, churn, cash pressure, and execution gaps.",
        "category": "business intelligence",
        "visual_style": "diagram:decision_grid",
        "visual_prompt": "Map founder blind spots into data checks: cash, churn, sales quality, delivery, support.",
        "hashtags": ["#BusinessIntelligence", "#Founder", "#GrowthAnalytics", "#DataForBusiness", "#Startup", "#Analytics"],
    },
    {
        "topic": "A data analyst should explain the cost of waiting, not only the size of the problem.",
        "summary": "Analysis becomes commercial when it shows what delay will cost the team.",
        "category": "business analytics",
        "visual_style": "insight_card:focus_strip",
        "visual_prompt": "Show problem size versus cost of waiting and the recommended next action.",
        "hashtags": ["#BusinessAnalytics", "#DecisionSupport", "#DataAnalytics", "#Growth", "#Operations", "#Leadership"],
    },
    {
        "topic": "Remote data talent wins when the work is easy to inspect.",
        "summary": "A strong portfolio makes the thinking, files, assumptions, and outputs visible.",
        "category": "remote data careers",
        "visual_style": "insight_card:editorial",
        "visual_prompt": "Show portfolio proof as problem, dataset, method, output, business interpretation.",
        "hashtags": ["#RemoteWork", "#DataCareer", "#Freelance", "#AnalyticsPortfolio", "#GitHub", "#DataAnalytics"],
    },
    {
        "topic": "The underrated skill in analytics is knowing what not to measure.",
        "summary": "Every extra metric competes for attention, and attention is expensive in business meetings.",
        "category": "analytics strategy",
        "visual_style": "diagram:decision_grid",
        "visual_prompt": "Create a metric pruning framework: keep, combine, investigate, remove.",
        "hashtags": ["#AnalyticsStrategy", "#KPIReporting", "#DataLeadership", "#BusinessIntelligence", "#DecisionMaking", "#DataAnalytics"],
    },
    {
        "topic": "Customer retention is a better growth story than vanity acquisition numbers.",
        "summary": "New users are attractive, but repeat behavior is where business quality starts showing.",
        "category": "customer analytics",
        "visual_style": "insight_card:stacked_grid",
        "visual_prompt": "Compare acquisition, repeat behavior, support pressure, and profit quality.",
        "hashtags": ["#CustomerRetention", "#GrowthAnalytics", "#CustomerAnalytics", "#BusinessGrowth", "#DataAnalytics", "#Retention"],
    },
    {
        "topic": "The real flex is turning a raw CSV into a decision someone can act on.",
        "summary": "Tools matter, but the business interpretation is what makes analysis valuable.",
        "category": "analytics portfolio",
        "visual_style": "insight_card:grid_strategic",
        "visual_prompt": "Show the journey from raw CSV to cleaned data, KPI, insight, recommendation, and action.",
        "hashtags": ["#AnalyticsPortfolio", "#DataAnalytics", "#Python", "#Excel", "#BusinessIntelligence", "#DataForBusiness"],
    },
    {
        "topic": "Data storytelling is not making charts emotional. It is making decisions obvious.",
        "summary": "A good data story removes confusion about what changed, why it matters, and what to do next.",
        "category": "data storytelling",
        "visual_style": "insight_card:editorial",
        "visual_prompt": "Show data storytelling as change, meaning, risk, and next action.",
        "hashtags": ["#DataStorytelling", "#DataViz", "#BusinessIntelligence", "#DecisionSupport", "#Analytics", "#Communication"],
    },
    {
        "topic": "When teams argue about numbers, the problem is usually definitions.",
        "summary": "Before building another dashboard, fix how the team defines customer, churn, revenue, and active use.",
        "category": "data quality",
        "visual_style": "insight_card:focus_strip",
        "visual_prompt": "Show conflicting metric definitions becoming one trusted reporting language.",
        "hashtags": ["#DataQuality", "#Metrics", "#BusinessIntelligence", "#DataGovernance", "#Analytics", "#KPIReporting"],
    },
    {
        "topic": "AI will not save a reporting process that nobody owns.",
        "summary": "Automation helps only when definitions, review points, and decision owners are already clear.",
        "category": "AI for analytics",
        "visual_style": "diagram:decision_grid",
        "visual_prompt": "Show AI-assisted reporting with human ownership, review checks, and decision accountability.",
        "hashtags": ["#AIForAnalytics", "#ReportingAutomation", "#DataOps", "#BusinessIntelligence", "#DataGovernance", "#Analytics"],
    },
    {
        "topic": "Speed versus accuracy is the analytics trade-off nobody wants to admit.",
        "summary": "Some decisions need a fast directional answer, while others need audited precision.",
        "category": "analytics tradeoffs",
        "visual_style": "diagram:tradeoff_matrix",
        "visual_prompt": "Build a speed versus accuracy matrix for analytics decisions.",
        "hashtags": ["#Analytics", "#Tradeoffs", "#DecisionMaking", "#DataQuality", "#BusinessIntelligence", "#Execution"],
    },
    {
        "topic": "Automating bad reporting just makes bad decisions arrive faster.",
        "summary": "Before automation, teams need definitions, data checks, exception rules, and owners.",
        "category": "reporting governance",
        "visual_style": "diagram:clarity_tier",
        "visual_prompt": "Show reporting automation gates: definition, quality check, owner, escalation, review.",
        "hashtags": ["#ReportingAutomation", "#DataGovernance", "#DataQuality", "#DataOps", "#Analytics", "#BusinessIntelligence"],
    },
    {
        "topic": "Data governance starts when two teams define the same metric differently.",
        "summary": "Governance is not paperwork. It is the operating system for trusted decisions.",
        "category": "data governance",
        "visual_style": "diagram:clarity_tier",
        "visual_prompt": "Show metric conflict becoming governed definitions, ownership, and escalation.",
        "hashtags": ["#DataGovernance", "#DataQuality", "#BusinessIntelligence", "#KPIReporting", "#Analytics", "#Management"],
    },
    {
        "topic": "Not every metric deserves a dashboard.",
        "summary": "If nobody will act when a metric changes, it belongs in an audit log, not an executive view.",
        "category": "analytics tradeoffs",
        "visual_style": "diagram:tradeoff_matrix",
        "visual_prompt": "Show metric triage: dashboard, deep dive, audit log, remove.",
        "hashtags": ["#DashboardDesign", "#KPIReporting", "#AnalyticsStrategy", "#DecisionSupport", "#BusinessIntelligence", "#DataLeadership"],
    },
    {
        "topic": "Every dashboard should have an escalation rule.",
        "summary": "A red KPI is not useful unless the team knows who acts and how fast.",
        "category": "analytics governance",
        "visual_style": "diagram:risk_loop",
        "visual_prompt": "Show a dashboard escalation loop: threshold, alert, owner, action, review.",
        "hashtags": ["#DataGovernance", "#KPIReporting", "#RiskManagement", "#DecisionSupport", "#Analytics", "#Operations"],
    },
]



class LinkedInAIAgent:
    def __init__(
        self,
        config: AgentConfig,
        gemini: GeminiClient | None = None,
        linkedin: LinkedInClient | None = None,
    ) -> None:
        self.config = config
        self.history = PublicationHistory(config.state_dir, config.reports_dir)
        self.gemini = gemini
        self.linkedin = linkedin

    def _rotation_state_path(self) -> Path:
        return self.config.state_dir / "weekday_rotation_state.json"

    @staticmethod
    def _rotation_week_position(weekday_index: int) -> int:
        return max(0, (weekday_index - 1) // 5)

    @staticmethod
    def _pick_special_weekday_for_week(_week_position: int) -> int:
        seeded = random.SystemRandom()
        return seeded.randint(1, 5)

    def _weekday_rotation_state(self) -> tuple[int, int]:
        today = datetime.now().date().isoformat()
        today_is_weekday = datetime.now().weekday() < 5
        state = {"weekday_index": 0, "weekday_last_active_day": "", "weekday_special_day": 0}
        path = self._rotation_state_path()
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    value = payload.get("weekday_index")
                    if isinstance(value, int):
                        state["weekday_index"] = value
                    last_day = payload.get("weekday_last_active_day")
                    if isinstance(last_day, str):
                        state["weekday_last_active_day"] = last_day
                    special_day = payload.get("weekday_special_day")
                    if isinstance(special_day, int):
                        state["weekday_special_day"] = special_day
            except Exception:
                state = {"weekday_index": 0, "weekday_last_active_day": "", "weekday_special_day": 0}
        if not today_is_weekday:
            return state.get("weekday_index", 0), state.get("weekday_special_day", 0)
        if state["weekday_last_active_day"] == today:
            return state.get("weekday_index", 0), state.get("weekday_special_day", 0)
        else:
            state["weekday_index"] += 1
            state["weekday_last_active_day"] = today
            week_position = self._rotation_week_position(state["weekday_index"])
            if ((state["weekday_index"] - 1) % 5) == 0:
                state["weekday_special_day"] = self._pick_special_weekday_for_week(week_position)
            elif not state["weekday_special_day"]:
                state["weekday_special_day"] = self._pick_special_weekday_for_week(week_position)
            state["updated_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
            return state.get("weekday_index", 0), state.get("weekday_special_day", 0)

    @staticmethod
    def _required_bucket(weekday_index: int, special_weekday: int) -> str | None:
        if not weekday_index:
            return None
        if ((weekday_index - 1) % 5) + 1 != special_weekday:
            return None
        week_position = (weekday_index - 1) // 5
        if week_position % 2 == 0:
            return "tradeoff"
        return "governance"

    @staticmethod
    def _candidate_bucket(candidate: TrendCandidate, visual_style: str | None = None) -> str | None:
        text = f"{candidate.topic} {candidate.summary} {candidate.category} {visual_style or ''}".lower()
        for topic_data in FALLBACK_TOPIC_LIBRARY:
            if topic_data["topic"] == candidate.topic:
                style = topic_data["visual_style"].lower()
                if "tradeoff" in style:
                    return "tradeoff"
                if any(token in style for token in ("clarity_tier", "risk_loop", "snapshot_ready")):
                    return "governance"
        if any(token in text for token in ("trade-off", "tradeoff", "tradeoffs", "trade off", "versus")):
            return "tradeoff"
        if any(token in text for token in ("governance", "controls", "audit", "risk", "compliance", "policy", "quality", "issue log", "data governance")):
            return "governance"
        return None

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

    def _fallback_trend_candidates(self, required_bucket: str | None = None) -> list[TrendCandidate]:
        sources = [
            EvidenceSource(
                title="Almond Owolabi Portfolio",
                url=PORTFOLIO_LINK,
                source_type="primary",
                publisher="Portfolio",
            ),
            EvidenceSource(
                title="LinkedIn AI Agent Repository",
                url=GITHUB_REPO_LINK,
                source_type="independent",
                publisher="GitHub",
            ),
            EvidenceSource(
                title="Retail Revenue Command Center",
                url=FEATURED_DASHBOARD_LINK,
                source_type="independent",
                publisher="GitHub",
            ),
        ]
        candidates: list[TrendCandidate] = []
        for topic_data in FALLBACK_TOPIC_LIBRARY:
            candidates.append(
                TrendCandidate(
                    topic=topic_data["topic"],
                    category=topic_data["category"],
                    summary=topic_data["summary"],
                    recency_score=1.0,
                    relevance_score=0.98,
                    evidence_score=1.0,
                    practical_value_score=0.99,
                    novelty_score=0.95,
                    sources=sources,
                )
            )
        random.Random(datetime.now().strftime("%Y-%m-%d")).shuffle(candidates)
        if required_bucket:
            filtered = [candidate for candidate in candidates if self._candidate_bucket(candidate) == required_bucket]
            if filtered:
                candidates = filtered
        deduped = [candidate for candidate in candidates if not self.history.is_duplicate(candidate.topic, self.config.duplicate_lookback_days)]
        return deduped

    def _fallback_visual_profile(self, candidate: TrendCandidate) -> dict[str, Any]:
        for entry in FALLBACK_TOPIC_LIBRARY:
            if entry["topic"] == candidate.topic:
                return {
                    "visual_style": entry["visual_style"],
                    "visual_prompt": entry["visual_prompt"],
                    "hashtags": entry["hashtags"],
                }
        seed = int(hashlib.sha256(candidate.topic.encode("utf-8")).hexdigest()[:16], 16)
        style_variants = [
            "diagram:decision_grid",
            "diagram:risk_loop",
            "diagram:clarity_tier",
            "diagram:tradeoff_matrix",
            "insight_card:focus_strip",
            "insight_card:stacked_grid",
            "insight_card:editorial",
            "insight_card:grid_strategic",
        ]
        style = style_variants[seed % len(style_variants)]
        return {
            "visual_style": style,
            "visual_prompt": "Use a practical decision-first visual style with clear action orientation.",
            "hashtags": ["#DataAnalytics", "#KPIReporting", "#DashboardDesign", "#DecisionSupport", "#GrowthAnalytics", "#BusinessIntelligence"],
        }

    @staticmethod
    def _visual_base_and_variant(style: str) -> tuple[str, str]:
        if ":" in style:
            base, variant = style.split(":", 1)
            return base, variant
        return style, "default"

    @staticmethod
    def _pick_fallback_candidate(fallback_list: list[TrendCandidate]) -> TrendCandidate:
        if not fallback_list:
            raise RuntimeError("Fallback list cannot be empty.")
        seed = hashlib.sha256(datetime.now().date().isoformat().encode("utf-8")).hexdigest()
        return fallback_list[int(seed[:16], 16) % len(fallback_list)]

    def _fallback_draft(self, candidate: TrendCandidate) -> DraftPost:
        profile = self._fallback_visual_profile(candidate)
        bucket = self._candidate_bucket(candidate, profile["visual_style"])
        if bucket in {"tradeoff", "governance"}:
            body = f"""Some analytics problems are not technical. They are judgment problems.

{candidate.topic}

{candidate.summary}

Why this matters

This is the part of data work people avoid because it is uncomfortable. A chart can show movement, but it cannot choose the trade-off for the team. Someone still has to decide whether speed matters more than accuracy, whether growth matters more than margin, whether automation is safe enough, or whether a metric is trusted enough to guide action.

That is where a serious analyst becomes valuable.

Where weak reporting fails

A weak report says: the number went up.

A stronger report says: the number went up, but the cost, risk, or customer signal moved in a direction that should change the plan.

The second version is harder to write because it forces accountability. It asks who owns the metric, what threshold matters, what action should happen next, and what risk the business is accepting if nothing changes.

This is also why governance is not just paperwork. In practical analytics, governance is the difference between a dashboard people admire and a report people trust. If two teams define the same KPI differently, the issue is not a visualization issue. It is a decision risk.

For freelancers, remote workers, and digital talent, this is a major positioning point. Do not sell yourself as someone who can only build reports. That is too small. Sell the ability to make messy decisions clearer with data.

The visible work is usually:

- clean the data
- build the dashboard
- send the report

The valuable work is:

- define the metric
- explain the trade-off
- show the risk
- name the owner
- recommend the next action

That is the difference between being seen as a tool user and being trusted as a business partner.

My take

If a metric has no owner, no threshold, no review rhythm, and no consequence, it should not sit proudly on an executive dashboard. It should be fixed, parked, or removed.

Otherwise, the team is not managing performance. It is decorating uncertainty.

Better data work does not make the room louder. It makes the next move harder to ignore."""
        else:
            body = f"""Data work should not stop at \"I found an insight.\"

{candidate.topic}

{candidate.summary}

Why this matters

The real value is helping a business decide what to do next. That can mean cleaning a messy file, defining the right KPI, finding a growth leak, explaining customer behavior, or turning a confusing report into one clear management action.

The common mistake

This is where a lot of analysts play too small. They show charts, but they do not force a decision. They list tools, but they do not show judgment. They talk about data, but they do not connect it to revenue, retention, cost, speed, quality, or risk.

A business does not care that the table was cleaned in Python if the output still does not answer a commercial question.

It does not care that the dashboard has nice colors if the leadership team still leaves the meeting asking what changed.

It does not care that the model is complex if nobody can explain what action should happen when the result moves.

That is why good data work needs a sharper standard.

Before touching the tool, ask:

- What decision is this supposed to improve?
- Who will use the answer?
- What metric will prove the answer mattered?
- What action should happen if the number moves?
- What should be ignored because it creates noise?

This is the kind of thinking that makes data useful for business growth. Growth is not only more sales. It can be better retention, fewer refunds, faster fulfillment, cleaner customer segments, stronger pricing decisions, better campaign focus, or less reporting waste.

The analyst who can explain that clearly will stand out more than the analyst who only says "I know Excel, SQL, Python, and Power BI."

Tools are expected now.

Judgment is the differentiator.

If you are building a data career, working remotely, freelancing, or trying to attract better clients, stop presenting yourself as a chart maker. That positioning is weak. Present yourself as someone who can take messy data, find the business signal, explain the trade-off, and help the team move.

That is a stronger brand.

That is also a stronger service.

My practical rule

Every analysis should end with one of three things:

- keep doing this
- stop doing this
- change this now

If it ends with "interesting insight", it probably was not sharp enough.

Make the data useful enough that the next decision becomes obvious."""

        return DraftPost(
            topic=candidate.topic,
            category=candidate.category,
            body=body,
            hashtags=profile["hashtags"],
            primary_source_url="",
            supporting_source_urls=[],
            claims=[
                "Curated weekday opinion post for LinkedIn engagement.",
                "The post is positioned around practical data analysis, business intelligence, and decision support.",
                "The post intentionally avoids forced external links unless the selected topic is specifically portfolio-focused.",
                "The content is designed to invite discussion from clients, recruiters, founders, and analytics teams.",
            ],
            visual_style="illustration" if self.config.allow_ai_illustrations else profile["visual_style"],
            visual_prompt=(
                f"Create a premium content-led LinkedIn infographic for this argument: {candidate.topic} {candidate.summary}. "
                f"Visual direction: {self.config.visual_direction} "
                f"Avoid: {', '.join(self.config.visual_avoid)}. "
                "The visual must explain the post idea clearly to an average reader in seconds. "
                "Use square or landscape format depending on what best fits the concept. "
                "Do not show a generic person staring at a laptop, stock office photo, abstract unlabeled metaphor, or text-only quote card. "
                "All text must be correctly spelled, large enough to read, and directly tied to the post."
            ),
            alt_text=f"Clear LinkedIn infographic explaining the data analytics argument: {candidate.topic}",
        )

    def _render_visual(self, draft: DraftPost) -> VisualAsset:
        if self.config.visual_provider == "codex_manual":
            path = self._codex_manual_visual_path(draft)
            visual = reviewed_visual(draft, path)
            self._ensure_visual_not_reused(path, self._visual_sha256(path))
            return visual
        asset_path = self._visual_path(draft)
        style, variant = self._visual_base_and_variant(draft.visual_style)
        if style == "illustration" and self.config.allow_ai_illustrations:
            gemini = self.gemini or GeminiClient()
            gemini.generate_illustration(self.config, draft, asset_path)
        elif style == "diagram":
            self._render_with_optional_variant(render_diagram, draft, asset_path, variant)
        elif style == "insight_card":
            self._render_with_optional_variant(render_insight_card, draft, asset_path, variant)
        elif style == "illustration":
            self._render_with_optional_variant(render_insight_card, draft, asset_path, variant)
        else:
            self._render_with_optional_variant(render_insight_card, draft, asset_path, variant)
        return validate_visual(asset_path, draft.alt_text)

    def _render_with_optional_variant(self, renderer, draft: DraftPost, asset_path: Path, variant: str) -> None:
        if "variant" in inspect.signature(renderer).parameters:
            renderer(draft, self.config, asset_path, variant=variant)
            return
        renderer(draft, self.config, asset_path)

    def generate_draft(self, candidate: TrendCandidate) -> DraftPost:
        gemini = self.gemini or GeminiClient()
        draft = gemini.generate_post(self.config, candidate)
        for attempt in range(3):
            normalize_draft(draft)
            draft.visual_prompt += (
                f"\nRequired visual direction: {self.config.visual_direction} "
                f"Avoid: {', '.join(self.config.visual_avoid)}."
            ) if self.config.visual_direction not in draft.visual_prompt else ""
            reasons = validate_draft(draft, self.config).reasons
            try:
                self._ensure_original_draft(draft)
            except RuntimeError as exc:
                reasons.append(str(exc))
            if not reasons:
                return draft
            if attempt < 2:
                draft = gemini.revise_post(self.config, candidate, draft, reasons)
        raise ValueError("Draft revision failed validation: " + "; ".join(reasons))

    def generate(self, candidate: TrendCandidate) -> tuple[DraftPost, VisualAsset]:
        draft = self.generate_draft(candidate)
        return draft, self._render_visual(draft)

    def _select_draft(self) -> tuple[TrendCandidate, DraftPost, list[dict[str, Any]]]:
        if self.config.content_mode == "mixed":
            history = self.history.load()
            previous = history[-1] if history else {}
            first = "researched" if previous.get("category") == "portfolio" else "portfolio"
            failures = []
            for mode in (first, "portfolio" if first == "researched" else "researched"):
                try:
                    return LinkedInAIAgent(replace(self.config, content_mode=mode), self.gemini, self.linkedin)._select_draft()
                except Exception as exc:
                    failures.append(f"{mode}: {exc}")
            raise RuntimeError("No fresh source-backed draft passed validation. " + "; ".join(failures))
        if self.config.content_mode == "portfolio":
            history = self.history.load()
            projects = GitHubProjects(self.config.github_owner, self.config.portfolio_excluded_terms).collect(self.config.portfolio_repositories, history)
            gemini = self.gemini or GeminiClient()
            failures = []
            # A rejected idea moves to a fresh angle; it does not recycle old copy.
            visited = set()
            for batch in range(4):
                candidates = gemini.portfolio_candidates(self.config, projects, history)
                for candidate in candidates:
                    if self.history.is_duplicate(candidate.topic, self.config.duplicate_lookback_days):
                        continue
                    try:
                        draft = self.generate_draft(candidate)
                        allowed = {source.url for source in candidate.sources}
                        if draft.primary_source_url != candidate.sources[0].url:
                            raise ValueError("Portfolio draft must link the exact project repository.")
                        if not draft.supporting_source_urls or any(url not in allowed for url in draft.supporting_source_urls):
                            raise ValueError("Portfolio draft must cite inspected project files.")
                        return candidate, draft, [{"title": source.title, "url": source.url} for source in candidate.sources]
                    except (ValueError, RuntimeError) as exc:
                        failures.append(str(exc))
                # Try the next projects when every angle in this batch fails.
                visited.update(project['name'] for project in projects)
                remaining = [name for name in self.config.portfolio_repositories if name not in visited]
                if batch < 3:
                    projects = GitHubProjects(self.config.github_owner, self.config.portfolio_excluded_terms).collect(remaining, history, exclude=visited)
                else:
                    break
            raise RuntimeError("Fresh project angles did not pass validation. " + "; ".join(failures[-3:]))
        weekday, special = self._weekday_rotation_state()
        bucket = self._required_bucket(weekday, special)
        if self.config.content_mode == "researched":
            candidates, citations = self.research()
            if not citations:
                raise RuntimeError("Research returned no search grounding. Fresh verified sources are required.")
            # Preserve the occasional governance/trade-off emphasis without
            # recycling an exhausted topical bucket.
            candidates.sort(key=lambda item: self._candidate_bucket(item) != bucket if bucket else False)
            failures = []
            for candidate in candidates[:3]:
                try:
                    draft = self.generate_draft(candidate)
                    source_urls = {source.url for source in candidate.sources}
                    if not draft.primary_source_url or draft.primary_source_url not in source_urls:
                        raise ValueError("Draft primary source does not match the researched evidence.")
                    if any(url not in source_urls for url in draft.supporting_source_urls):
                        raise ValueError("Draft adds an unresearched supporting source.")
                    if any("curated weekday opinion post" in claim.lower() for claim in draft.claims):
                        raise ValueError("Researched posts cannot bypass the evidence gate as curated copy.")
                    return candidate, draft, citations
                except (ValueError, RuntimeError) as exc:
                    failures.append(str(exc))
            raise RuntimeError("No original researched draft passed review. " + "; ".join(failures))
        if self.config.content_mode != "curated":
            raise RuntimeError(f"Unknown content mode: {self.config.content_mode}")
        candidates = self._fallback_trend_candidates(bucket)
        if not candidates:
            raise RuntimeError("No curated weekday topic is available after duplicate checks.")
        candidate = self._pick_fallback_candidate(candidates)
        draft = self._fallback_draft(candidate)
        normalize_draft(draft)
        self._ensure_original_draft(draft)
        return candidate, draft, []

    def _pending_draft(self, persist: bool) -> dict[str, Any]:
        path = self.config.state_dir / "pending_image_post.json"
        if path.exists():
            pending = json.loads(path.read_text(encoding="utf-8"))
            draft = draft_from_dict(pending["draft"])
            replacement_reason = None
            try:
                self._ensure_original_draft(draft)
            except RuntimeError as exc:
                if str(exc).startswith(("Draft references excluded organisation", "Topic was covered", "Post repeats substantial")):
                    replacement_reason = str(exc)
                else:
                    raise
            if pending.get("created_at"):
                created = datetime.fromisoformat(pending["created_at"].replace("Z", "+00:00"))
                if datetime.now(timezone.utc) - created > timedelta(days=7):
                    replacement_reason = "Refresh sources and prepare a new draft after seven days."
            if not replacement_reason:
                return pending
            if persist:
                atomic_json(self.config.state_dir / "replaced_pending_post.json", {**pending, "replacement_reason": replacement_reason})
        candidate, draft, citations = self._select_draft()
        brief = write_visual_brief(draft, self._codex_manual_visual_path(draft))
        pending = {"status": "pending_image", "candidate": to_dict(candidate),
                   "draft": to_dict(draft), "citations": citations, "brief": str(brief),
                   "created_at": datetime.now(timezone.utc).isoformat()}
        if persist:
            atomic_json(path, pending)
            (self.config.state_dir / "approved_post.json").unlink(missing_ok=True)
        return pending

    def prepare_post(self) -> Path:
        """Prepare and persist an exact fresh draft, with no LinkedIn calls."""
        self._recover_publication()
        pending = self._pending_draft(persist=True)
        draft = draft_from_dict(pending["draft"])
        feedback_path = self.config.state_dir / "review_feedback.json"
        if feedback_path.exists():
            feedback = json.loads(feedback_path.read_text())
            if feedback.get("draft_sha256") == draft_sha256(draft) and feedback.get("note"):
                gemini = self.gemini or GeminiClient()
                candidate = trend_from_dict(pending["candidate"])
                revised = gemini.revise_post(self.config, candidate, draft,
                    ["Owner's required revision: " + feedback["note"],
                     "Revise the visual prompt too if the owner requested image changes. Preserve verified sources."])
                normalize_draft(revised)
                reasons = validate_draft(revised, self.config).reasons
                self._ensure_original_draft(revised)
                allowed = {source.url for source in candidate.sources}
                if revised.primary_source_url != draft.primary_source_url or any(url not in allowed for url in revised.supporting_source_urls):
                    reasons.append("Revision changed the verified source links.")
                revised.visual_prompt += f"\nRequired visual direction: {self.config.visual_direction}. Avoid: {', '.join(self.config.visual_avoid)}."
                if reasons:
                    raise ValueError("Revision needs correction: " + "; ".join(reasons))
                if draft_sha256(revised) == draft_sha256(draft):
                    raise ValueError("Requested revision did not change the draft or image brief.")
                pending.update(draft=to_dict(revised), status="pending_image", owner_feedback=feedback,
                               created_at=datetime.now(timezone.utc).isoformat())
                atomic_json(self.config.state_dir / "pending_image_post.json", pending)
                draft = revised
        return write_visual_brief(draft, self._codex_manual_visual_path(draft))

    def _approval_reason(self, draft: DraftPost, asset_sha256: str) -> str | None:
        """Approval belongs to exact post and image bytes, never a topic alone."""
        if not self.config.require_post_approval:
            return None
        path = self.config.state_dir / "approved_post.json"
        approval = json.loads(path.read_text()) if path.exists() else {}
        if (approval.get("draft_sha256") != draft_sha256(draft)
                or approval.get("asset_sha256") != asset_sha256
                or approval.get("approved_by") != "owner_local_review"
                or not approval.get("approved_at")):
            return "Review the exact post and image in your local dashboard and approve them before publication."
        feedback_path = self.config.state_dir / "review_feedback.json"
        if feedback_path.exists():
            feedback = json.loads(feedback_path.read_text())
            if (feedback.get("draft_sha256") == draft_sha256(draft)
                    and feedback.get("requested_at", "") >= approval["approved_at"]):
                return "Changes were requested after approval. Review the revised post and image."
        return None

    def _require_approval(self, draft: DraftPost, asset_sha256: str) -> None:
        reason = self._approval_reason(draft, asset_sha256)
        if reason:
            raise RuntimeError(reason)

    def _recover_publication(self) -> None:
        path = self.config.state_dir / "publication_attempt.json"
        if not path.exists():
            return
        journal = json.loads(path.read_text(encoding="utf-8"))
        if journal.get("status") == "publishing":
            raise RuntimeError("Previous LinkedIn publication has an uncertain outcome. Check LinkedIn before retrying; automatic reposting is blocked.")
        if journal.get("status") == "published":
            record = journal["record"]
            if not any(item.get("post_urn") == record["post_urn"] for item in self.history.load()):
                self.history.append(record)
            pending_path = self.config.state_dir / "pending_image_post.json"
            if pending_path.exists():
                pending = json.loads(pending_path.read_text())
                if pending.get("draft", {}).get("topic") == record.get("topic"):
                    pending_path.unlink()
                    (self.config.state_dir / "approved_post.json").unlink(missing_ok=True)

    def run(self, dry_run: bool) -> PublishResult:
        candidate = draft = None
        citations = []
        try:
            self._recover_publication()
            today = self.history.published_today(self.config.timezone)
            if today and not dry_run:
                return PublishResult(status="already_published", dry_run=False,
                                     topic=today["topic"], post_urn=today["post_urn"])
            pending = self._pending_draft(persist=not dry_run)
            candidate = trend_from_dict(pending["candidate"])
            draft = draft_from_dict(pending["draft"])
            citations = pending.get("citations", [])
            self._ensure_original_draft(draft)
            draft_report = validate_draft(draft, self.config)
            if not draft_report.passed:
                raise ValueError("; ".join(draft_report.reasons))
            try:
                visual = self._render_visual(draft)
                visual_path = Path(visual.path)
                visual_sha256 = self._visual_sha256(visual_path)
                self._ensure_visual_not_reused(visual_path, visual_sha256)
            except (RuntimeError, ValueError, OSError) as exc:
                if self.config.visual_provider != "codex_manual":
                    raise
                result = PublishResult(status="pending_image", dry_run=dry_run,
                                       topic=draft.topic, pending_reason=str(exc))
                pending.update(reason=str(exc), updated_at=result.created_at)
                if not dry_run:
                    atomic_json(self.config.state_dir / "pending_image_post.json", pending)
                result.report_path = str(write_report(self.config.reports_dir, {
                    **pending, "topic": draft.topic, "dry_run": dry_run, "publish": result,
                }))
                return result
            provider = "codex_imagegen" if self.config.visual_provider == "codex_manual" else self.config.visual_provider
            approval_reason = self._approval_reason(draft, visual_sha256)
            if approval_reason and not dry_run:
                return PublishResult(status="awaiting_approval", dry_run=False,
                                     topic=draft.topic, pending_reason=approval_reason)
            result = PublishResult(status="dry_run_ok" if dry_run else "published", dry_run=dry_run, topic=draft.topic)
            record = {"created_at": result.created_at, "topic": draft.topic, "body": draft.body,
                      "content_key": candidate.content_key,
                      "category": draft.category, "visual_path": str(visual_path),
                      "visual_sha256": visual_sha256, "visual_provider": provider,
                      "visual_signature": visual_signature(visual_path),
                      "primary_source_url": draft.primary_source_url}
            if not dry_run:
                linkedin = self.linkedin or LinkedInClient.from_env(self.config)
                result.image_urn = linkedin.upload_image(visual)
                visual.linkedin_image_urn = result.image_urn
                journal_path = self.config.state_dir / "publication_attempt.json"
                atomic_json(journal_path, {"status": "publishing", "topic": draft.topic,
                                          "started_at": result.created_at, "image_urn": result.image_urn})
                result.post_urn = linkedin.publish_post(draft, result.image_urn)
                record.update(post_urn=result.post_urn, image_urn=result.image_urn)
                atomic_json(journal_path, {"status": "published", "record": record})
                self.history.append(record)
                (self.config.state_dir / "pending_image_post.json").unlink(missing_ok=True)
                (self.config.state_dir / "approved_post.json").unlink(missing_ok=True)
            review = (json.loads(visual_path.with_suffix(".json").read_text(encoding="utf-8"))
                      if provider == "codex_imagegen" else None)
            report_path = write_report(self.config.reports_dir, {
                "status": result.status, "dry_run": dry_run, "selected_topic": candidate.topic,
                "trend": candidate, "draft": draft, "visual": visual,
                "visual_generation": {"provider": provider, "asset": str(visual_path),
                                      "asset_sha256": visual_sha256, "review": review, "alt_text": visual.alt_text},
                "gemini_grounding_citations": citations,
                "safety": {"trend": None, "draft": draft_report}, "publish": result,
                "owner_approval": {"required": self.config.require_post_approval, "reason": approval_reason},
            })
            result.report_path = str(report_path)
            return result
        except Exception as exc:
            result = self._skip(str(exc), candidate=candidate, draft=draft, citations=citations)
            result.dry_run = dry_run
            return result

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
1) What metric would you add before presenting this to leadership?
2) Do you prefer dashboards that explain the decision, or dashboards that only show the numbers?"""
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
        if self.config.require_post_approval and not dry_run:
            return PublishResult(status="awaiting_approval", dry_run=False,
                                 pending_reason="Use the local review dashboard and scheduled publisher for approved posts.")
        draft = self.featured_dashboard_draft()
        draft_report = validate_draft(draft, self.config)
        if not draft_report.passed:
            return self._skip("; ".join(draft_report.reasons), draft=draft, citations=[])
        try:
            visual = validate_visual(self.config.assets_dir / FEATURED_DASHBOARD_IMAGE, draft.alt_text, allow_landscape=True)
            visual_path = Path(visual.path)
            visual_sha256 = self._visual_sha256(visual_path)
            self._ensure_visual_not_reused(visual_path, visual_sha256)
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
                        "visual_path": str(visual_path),
                        "visual_sha256": visual_sha256,
                        "visual_provider": "featured_dashboard",
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
        if self.config.visual_provider == "codex_manual":
            self._check_staged_codex_visual(draft, image_path)
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
        if self.config.require_post_approval:
            raise RuntimeError("Use the local review dashboard and scheduled publisher for approved posts.")
        path = self.config.state_dir / "pending_post.json"
        if not path.exists():
            raise RuntimeError("No staged preview exists. Run the preview command first.")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("status") != "pending":
            raise RuntimeError(f"The staged preview is {payload.get('status', 'invalid')} and cannot be published again.")

        draft = draft_from_dict(payload.get("draft", {}))
        self._ensure_original_draft(draft)
        visual = visual_from_dict(payload.get("visual", {}))
        draft_report = validate_draft(draft, self.config)
        if not draft_report.passed:
            raise RuntimeError("Staged post failed the writing gate: " + "; ".join(draft_report.reasons))
        if self.config.visual_provider == "codex_manual":
            checked_visual = self._check_staged_codex_visual(draft, Path(visual.path))
        else:
            checked_visual = validate_visual(Path(visual.path), visual.alt_text)
        visual_path = Path(visual.path)
        actual_hash = self._visual_sha256(visual_path)
        if actual_hash != payload.get("image_sha256"):
            raise RuntimeError("The staged image changed after preview. Generate and review a new preview.")
        self._ensure_visual_not_reused(visual_path, actual_hash)

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
                "body": draft.body,
                "category": draft.category,
                "post_urn": post_urn,
                "image_urn": image_urn,
                "visual_path": str(visual_path),
                "visual_sha256": actual_hash,
                "visual_provider": "staged_preview",
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

    def _codex_manual_visual_path(self, draft: DraftPost) -> Path:
        slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in draft.topic).strip("-")[:70] or "weekday"
        return self.config.assets_dir / f"codex_weekday_{slug}.png"

    def _check_staged_codex_visual(self, draft: DraftPost, image_path: Path) -> VisualAsset:
        expected = self._codex_manual_visual_path(draft)
        if image_path.resolve() != expected.resolve():
            raise RuntimeError("Staged image is not the reviewed Codex asset for this topic.")
        return reviewed_visual(draft, expected)

    def prepare_visual(self, topic: str | None = None) -> Path:
        """Write an exact draft handoff without generating or publishing an image."""
        pending_path = self.config.state_dir / "pending_image_post.json"
        if pending_path.exists() and not topic:
            pending = json.loads(pending_path.read_text(encoding="utf-8"))
            draft = draft_from_dict(pending["draft"])
            self._ensure_original_draft(draft)
            return write_visual_brief(draft, self._codex_manual_visual_path(draft))
        if topic:
            candidates = [c for c in self._fallback_trend_candidates() if c.topic == topic]
            if not candidates:
                raise RuntimeError("No eligible curated topic is available for this visual brief.")
            draft = self._fallback_draft(candidates[0])
            normalize_draft(draft)
        else:
            _, draft, _ = self._select_draft()
        self._ensure_original_draft(draft)
        return write_visual_brief(draft, self._codex_manual_visual_path(draft))

    def _ensure_original_draft(self, draft: DraftPost) -> None:
        if excluded_material(" ".join([draft.topic, draft.body, draft.visual_prompt, draft.alt_text]), self.config.portfolio_excluded_terms):
            raise RuntimeError("Draft references excluded organisation work. Select a different personal project.")
        if self.history.is_duplicate(draft.topic, self.config.duplicate_lookback_days):
            raise RuntimeError("Topic was covered recently. Prepare an original post before publishing.")
        similar_topic = self.history.similar_body_topic(draft.body, self.config.duplicate_lookback_days)
        if similar_topic:
            raise RuntimeError(f"Post repeats substantial wording from '{similar_topic}'. Write a fresh draft before publishing.")

    def _visual_sha256(self, asset_path: Path) -> str:
        return hashlib.sha256(asset_path.read_bytes()).hexdigest()

    def _ensure_visual_not_reused(self, asset_path: Path, visual_sha256: str) -> None:
        fingerprints = self.history.recent_visual_fingerprints(self.config.duplicate_lookback_days)
        if str(asset_path) in fingerprints or visual_sha256 in fingerprints:
            raise RuntimeError(
                "This generated image was already used recently. "
                "Create a new topic-specific visual before posting."
            )
        signature = int(visual_signature(asset_path), 16)
        for item in self.history.load():
            previous = item.get("visual_signature")
            if previous and bin(signature ^ int(previous, 16)).count("1") <= 12:
                raise RuntimeError("This image is visually too similar to a published image. Create a substantially different visual.")

    def _render_visual_to_path(self, draft: DraftPost, asset_path: Path) -> None:
        style, variant = self._visual_base_and_variant(draft.visual_style)
        if style == "diagram":
            self._render_with_optional_variant(render_diagram, draft, asset_path, variant)
            return
        self._render_with_optional_variant(render_insight_card, draft, asset_path, variant)


def token_metadata(expires_in: int) -> dict[str, str]:
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    return {"expires_at": expires_at.isoformat(timespec="seconds").replace("+00:00", "Z")}


def normalize_draft(draft: DraftPost) -> None:
    draft.hashtags = [tag if tag.startswith("#") else f"#{tag}" for tag in draft.hashtags[:10] if tag.strip()]
    draft.supporting_source_urls = dedupe_urls(draft.supporting_source_urls)[:3]
    draft.alt_text = normalize_alt_text(draft.alt_text, draft.topic, draft.visual_style)


def normalize_alt_text(alt_text: str, topic: str, visual_style: str) -> str:
    cleaned = " ".join((alt_text or "").split())
    if not cleaned:
        style = visual_style.split(":", 1)[0]
        if style == "diagram":
            style = "diagram"
        elif style == "insight_card":
            style = "insight card"
        else:
            style = "insight card"
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
