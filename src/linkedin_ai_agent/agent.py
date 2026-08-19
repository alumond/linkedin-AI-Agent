from __future__ import annotations

import hashlib
import inspect
import json
import os
import random
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
        self.history = PublicationHistory(config.state_dir)
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
        return deduped if deduped else candidates

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
                "Use the clean workflow/explainer style: light background, strong title, numbered cards or clearly separated sections, "
                "simple icons, arrows only where movement matters, short readable captions, and a concise takeaway area. "
                "The visual must explain the post idea clearly to an average reader in seconds. "
                "Use square or landscape format depending on what best fits the concept. "
                "Do not show a generic person staring at a laptop, stock office photo, abstract unlabeled metaphor, or text-only quote card. "
                "All text must be correctly spelled, large enough to read, and directly tied to the post."
            ),
            alt_text=f"Clear LinkedIn infographic explaining the data analytics argument: {candidate.topic}",
        )

    def _render_visual(self, draft: DraftPost) -> VisualAsset:
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
        visual = self._render_visual(draft)
        return draft, visual

    def run(self, dry_run: bool) -> PublishResult:
        weekday_index, special_weekday = self._weekday_rotation_state()
        required_bucket = self._required_bucket(weekday_index, special_weekday)
        fallback_list = self._fallback_trend_candidates(required_bucket)
        if not fallback_list:
            return self._skip("No curated weekday topic is available after duplicate checks.", citations=[])
        candidate = self._pick_fallback_candidate(fallback_list)
        draft: DraftPost | None = None
        try:
            draft = self._fallback_draft(candidate)
            normalize_draft(draft)
            draft_report = validate_draft(draft, self.config)
            if not draft_report.passed:
                return self._skip("; ".join(draft_report.reasons), candidate=candidate, citations=[], draft=draft)
            if self.config.visual_provider == "codex_manual":
                codex_asset = self._codex_manual_visual_path(draft)
                if codex_asset.exists():
                    visual_generation_provider = "codex_manual_topic_asset"
                    visual = validate_visual(codex_asset, draft.alt_text)
                else:
                    raise RuntimeError(
                        "A Codex-generated topic-specific image is required before posting or dry-running. "
                        f"Missing topic image: {codex_asset}."
                    )
                visual_sha256 = self._visual_sha256(codex_asset)
                self._ensure_visual_not_reused(codex_asset, visual_sha256)
                result = PublishResult(
                    status="dry_run_ok" if dry_run else "published",
                    dry_run=dry_run,
                    topic=draft.topic,
                    post_urn=None,
                    image_urn=None,
                )
                if not dry_run:
                    linkedin = self.linkedin or LinkedInClient.from_env(self.config)
                    image_urn = linkedin.upload_image(visual)
                    visual.linkedin_image_urn = image_urn
                    post_urn = linkedin.publish_post(draft, image_urn)
                    result.post_urn = post_urn
                    result.image_urn = image_urn
                report_path = write_report(
                    self.config.reports_dir,
                    {
                        "status": result.status,
                        "dry_run": dry_run,
                        "selected_topic": candidate.topic,
                        "trend": candidate,
                        "draft": draft,
                        "visual": visual,
                        "visual_generation": {
                            "provider": visual_generation_provider,
                            "asset": str(codex_asset),
                            "asset_sha256": visual_sha256,
                            "prompt": draft.visual_prompt,
                            "alt_text": draft.alt_text,
                        },
                        "gemini_grounding_citations": [],
                        "safety": {"trend": None, "draft": draft_report},
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
                            "post_urn": result.post_urn,
                            "image_urn": result.image_urn,
                            "visual_path": str(codex_asset),
                            "visual_sha256": visual_sha256,
                            "visual_provider": visual_generation_provider,
                            "primary_source_url": draft.primary_source_url,
                            "report_path": str(report_path),
                        }
                    )
                return result
            visual = self._render_visual(draft)
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
            payload = {
                "status": result.status,
                "dry_run": dry_run,
                "selected_topic": candidate.topic,
                "trend": candidate,
                "draft": draft,
                "visual": visual,
                "gemini_grounding_citations": [],
                "safety": {"trend": None, "draft": draft_report},
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
                        "visual_path": str(visual_path),
                        "visual_sha256": visual_sha256,
                        "visual_provider": self.config.visual_provider,
                        "primary_source_url": draft.primary_source_url,
                        "report_path": str(report_path),
                    }
                )
            return result
        except Exception as exc:
            return self._skip(str(exc), candidate=candidate, draft=draft, citations=[])

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

    def _visual_sha256(self, asset_path: Path) -> str:
        return hashlib.sha256(asset_path.read_bytes()).hexdigest()

    def _ensure_visual_not_reused(self, asset_path: Path, visual_sha256: str) -> None:
        fingerprints = self.history.recent_visual_fingerprints(self.config.duplicate_lookback_days)
        if str(asset_path) in fingerprints or visual_sha256 in fingerprints:
            raise RuntimeError(
                "This generated image was already used recently. "
                "Create a new topic-specific visual before posting."
            )

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
