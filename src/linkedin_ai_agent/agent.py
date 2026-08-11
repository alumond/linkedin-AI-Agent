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


FALLBACK_TOPIC_LIBRARY = [
    {
        "topic": "Revenue growth is useless if profit, retention, and returns are moving in the wrong direction.",
        "summary": "Build dashboards that expose growth quality, not just volume.",
        "category": "analytics",
        "visual_style": "diagram:decision_grid",
        "visual_prompt": "Use a decision flow map to test if growth, margin, retention, and returns agree before declaring success.",
        "hashtags": [
            "#DataAnalytics",
            "#KPIReporting",
            "#GrowthLeadership",
            "#Retention",
            "#Profitability",
            "#DecisionScience",
        ],
    },
    {
        "topic": "A dashboard is not a chart collection. It is a decision system.",
        "summary": "Treat visuals as an executive decision layer, not a portfolio wallpaper.",
        "category": "dashboard design",
        "visual_style": "insight_card:editorial",
        "visual_prompt": "Show a clear decision hierarchy: signal, context, action, owner.",
        "hashtags": [
            "#DashboardDesign",
            "#DataViz",
            "#DecisionSupport",
            "#BusinessIntelligence",
            "#Analytics",
            "#DataStrategy",
        ],
    },
    {
        "topic": "What I learned building a retail revenue leakage dashboard from 2,160 synthetic rows.",
        "summary": "One portfolio artifact can validate analytics reasoning end-to-end.",
        "category": "analytics",
        "visual_style": "diagram:clarity_tier",
        "visual_prompt": "Lean into process flow: data generation, KPI model, leakage detection, and decision outputs.",
        "hashtags": [
            "#AnalyticsPortfolio",
            "#Python",
            "#RetailAnalytics",
            "#CommandCenter",
            "#DataForBusiness",
            "#KPIReporting",
        ],
    },
    {
        "topic": "Retention as the real revenue lever.",
        "summary": "The mistake many analysts make: showing KPIs without showing what management should do next.",
        "category": "KPI reporting",
        "visual_style": "diagram:risk_loop",
        "visual_prompt": "Lay out a clear loop that ties retention movement to revenue confidence.",
        "hashtags": [
            "#CustomerRetention",
            "#GrowthAnalytics",
            "#KPIReporting",
            "#BusinessGrowth",
            "#DataStorytelling",
            "#AnalyticsMindset",
        ],
    },
    {
        "topic": "Why repeat customers are often a better business signal than new customer volume.",
        "summary": "The real growth question is customer quality versus customer count.",
        "category": "business intelligence",
        "visual_style": "insight_card:stacked_grid",
        "visual_prompt": "Compare acquisition and repeat cohorts side-by-side and force a decision.",
        "hashtags": [
            "#BusinessIntelligence",
            "#CustomerAnalytics",
            "#GrowthModel",
            "#RetentionStrategy",
            "#DataLeadership",
            "#MEEnergy",
        ],
    },
    {
        "topic": "How returns and fulfillment delays quietly destroy revenue growth.",
        "summary": "Operational leak points often hide in support and fulfillment.",
        "category": "analytics",
        "visual_style": "diagram:snapshot_ready",
        "visual_prompt": "Map the end-to-end leak path and highlight the management intervention points.",
        "hashtags": [
            "#OperationalEfficiency",
            "#DataAnalytics",
            "#CustomerSatisfaction",
            "#Fulfillment",
            "#ReturnsManagement",
            "#RevenueLeakage",
        ],
    },
    {
        "topic": "A strong GitHub project should show business judgment, not only polished code.",
        "summary": "Proof of work is stronger when it shows business outcomes and decision logic.",
        "category": "portfolio strategy",
        "visual_style": "insight_card:focus_strip",
        "visual_prompt": "Use a portfolio credibility card that ties code, process, and board-level implications together.",
        "hashtags": [
            "#Portfolio",
            "#GitHub",
            "#DataPortfolio",
            "#DataLeadership",
            "#Freelance",
            "#BusinessResults",
        ],
    },
    {
        "topic": "If your dashboard has no business question, it is decoration.",
        "summary": "A dashboard with no action is just a chart gallery.",
        "category": "analytics",
        "visual_style": "diagram:tradeoff_matrix",
        "visual_prompt": "Use an urgent decision card format with 'What changed', 'Why it matters', and 'What we do now'.",
        "hashtags": [
            "#DecisionSupport",
            "#DataViz",
            "#BI",
            "#ExecutiveDashboard",
            "#DataLeadership",
            "#ImpactAnalytics",
        ],
    },
    {
        "topic": "The difference between a beginner dashboard and an executive dashboard.",
        "summary": "Density, hierarchy, and decision clarity are what separate amateurs from decision support.",
        "category": "dashboard design",
        "visual_style": "diagram:tradeoff_matrix",
        "visual_prompt": "Contrast two states: noisy visuals versus a single decision channel and action map.",
        "hashtags": [
            "#ExecutiveDashboard",
            "#ManagementReporting",
            "#DataVisual",
            "#PowerBI",
            "#Analytics",
            "#DecisionMaking",
        ],
    },
    {
        "topic": "How Monitoring and Evaluation taught me to prioritize retention and service quality.",
        "summary": "M&E discipline improves every business dashboard.",
        "category": "impact analytics",
        "visual_style": "insight_card:grid_strategic",
        "visual_prompt": "Structure a practical M&E lens with indicator, quality check, and intervention trigger.",
        "hashtags": [
            "#MonitoringEvaluation",
            "#ImpactAnalytics",
            "#ServiceQuality",
            "#DataGovernance",
            "#GrowthAnalytics",
            "#DecisionSupport",
        ],
    },
    {
        "topic": "What to automate first in reporting: cleaning, governance, or storytelling.",
        "summary": "Most teams fail fast because they automate the wrong link in the data chain.",
        "category": "analytics operations",
        "visual_style": "diagram:clarity_tier",
        "visual_prompt": "Show a realistic reporting stack and mark the highest-impact automation unlock.",
        "hashtags": [
            "#Reporting",
            "#DataOps",
            "#WorkflowAutomation",
            "#DataQuality",
            "#BI",
            "#Productivity",
        ],
    },
    {
        "topic": "Why your weekly metric review should start with questions, not numbers.",
        "summary": "Metrics are only useful when they force a manager decision within 24 hours.",
        "category": "decision support",
        "visual_style": "insight_card:editorial",
        "visual_prompt": "Frame each metric with the exact question it answers in leadership meetings.",
        "hashtags": [
            "#Management",
            "#KPIs",
            "#DataInAction",
            "#Leadership",
            "#BusinessAnalytics",
            "#DecisionMaking",
        ],
    },
    {
        "topic": "Portfolio-proof work beats resume-padding for getting data clients.",
        "summary": "Clients trust concrete outcomes more than a long self-description.",
        "category": "personal branding",
        "visual_style": "diagram:decision_grid",
        "visual_prompt": "Create a trust pyramid: problem, method, result, client impact.",
        "hashtags": [
            "#Freelance",
            "#Career",
            "#DataCareer",
            "#Portfolio",
            "#ClientAcquisition",
            "#Brand",
        ],
    },
    {
        "topic": "When your reporting speed increases but decision speed slows, you have a process gap.",
        "summary": "Fast visuals are useless if no one knows what action they require.",
        "category": "analytics",
        "visual_style": "insight_card:stacked_grid",
        "visual_prompt": "Show a response-time gap: publish cadence versus decision turnaround cadence.",
        "hashtags": [
            "#DecisionSpeed",
            "#DataOps",
            "#AnalyticsManagement",
            "#BusinessIntelligence",
            "#KPIReporting",
            "#Growth",
        ],
    },
    {
        "topic": "Data stories stop being useful when they avoid trade-offs.",
        "summary": "Every metric has a trade-off; the board wants to know which one to accept.",
        "category": "storytelling",
        "visual_style": "diagram:risk_loop",
        "visual_prompt": "Build a trade-off matrix for growth, margin, retention, and risk.",
        "hashtags": [
            "#DataStorytelling",
            "#Tradeoffs",
            "#ProductDecision",
            "#Analytics",
            "#KPITradeoff",
            "#Execution",
        ],
    },
    {
        "topic": "How to prove dashboard value with one weekly executive question.",
        "summary": "A dashboard is validated by the decision it changes.",
        "category": "analytics",
        "visual_style": "diagram:decision_grid",
        "visual_prompt": "Use a loop where the question, decision, action, and proof path are visible.",
        "hashtags": [
            "#ExecutiveReporting",
            "#BusinessIntelligence",
            "#KPIs",
            "#DataLeadership",
            "#ImpactTracking",
            "#DecisionSupport",
        ],
    },
    {
        "topic": "Decision fatigue in data meetings is a UX and process design failure.",
        "summary": "The board needs fewer ambiguous numbers and one clear call.",
        "category": "analytics operations",
        "visual_style": "insight_card:focus_strip",
        "visual_prompt": "Show one dominant insight with a strict call-to-action row.",
        "hashtags": [
            "#DecisionMaking",
            "#MeetingOptimization",
            "#DataLeadership",
            "#Management",
            "#DashboardDesign",
            "#KPIReporting",
        ],
    },
    {
        "topic": "Why your 'engagement' metrics are not a business KPI.",
        "summary": "If growth has no commercial signal attached, it is vanity.",
        "category": "growth strategy",
        "visual_style": "diagram:risk_loop",
        "visual_prompt": "Contrast audience attention with business outcome and call out the gap.",
        "hashtags": [
            "#GrowthAnalytics",
            "#BusinessKPI",
            "#DataStrategy",
            "#PerformanceManagement",
            "#Analytics",
            "#DecisionSupport",
        ],
    },
    {
        "topic": "Retention cliffs usually appear after 'good' quarter-end growth.",
        "summary": "Watch reactivation, repeat ratio, and support burden together before celebration.",
        "category": "customer analytics",
        "visual_style": "insight_card:stacked_grid",
        "visual_prompt": "Make retention lag visible next to growth and margin movement.",
        "hashtags": [
            "#CustomerRetention",
            "#KPIReporting",
            "#GrowthStrategy",
            "#Profitability",
            "#DataForBusiness",
            "#Analytics",
        ],
    },
    {
        "topic": "Portfolio work is marketing, not decoration: proof through process + outputs.",
        "summary": "Clients remember artifacts that can be audited, not slogans.",
        "category": "personal branding",
        "visual_style": "insight_card:editorial",
        "visual_prompt": "Show a clear artifact chain: dataset -> model -> decisions -> business test.",
        "hashtags": [
            "#DataPortfolio",
            "#Freelance",
            "#GitHub",
            "#CareerGrowth",
            "#BusinessResults",
            "#BrandBuilding",
        ],
    },
    {
        "topic": "Data teams lose value when they optimize for shiny dashboards over executive certainty.",
        "summary": "Shiny is nice; certainty drives decisions and budgets.",
        "category": "analytics leadership",
        "visual_style": "diagram:clarity_tier",
        "visual_prompt": "Build a clarity ladder: signal, confidence, actionability, and owner.",
        "hashtags": [
            "#AnalyticsLeadership",
            "#DecisionSupport",
            "#ExecutiveReporting",
            "#DataMaturity",
            "#BusinessIntelligence",
            "#Impact",
        ],
    },
    {
        "topic": "How to turn a reporting audit into a revenue call.",
        "summary": "Treat every report as a sales-enablement artifact.",
        "category": "data operations",
        "visual_style": "diagram:tradeoff_matrix",
        "visual_prompt": "Map speed, accuracy, cost, and reliability trade-offs with ownership.",
        "hashtags": [
            "#DataOperations",
            "#RevenueEnablement",
            "#BusinessAnalytics",
            "#DecisionMaking",
            "#KPIReporting",
            "#DataLeadership",
        ],
    },
    {
        "topic": "The first week of any analytics project should be a governance baseline.",
        "summary": "Without data contracts and issue logs, your model is noise.",
        "category": "analytics setup",
        "visual_style": "insight_card:grid_strategic",
        "visual_prompt": "Show governance gates: source contract, QA, anomaly watch, escalation.",
        "hashtags": [
            "#DataQuality",
            "#MLOps",
            "#AnalyticsOperations",
            "#Governance",
            "#DecisionReadiness",
            "#BI",
        ],
    },
    {
        "topic": "If your dashboard is hard to screenshot, it is hard to trust.",
        "summary": "The best dashboards are built for boardroom consumption.",
        "category": "dashboard design",
        "visual_style": "diagram:snapshot_ready",
        "visual_prompt": "Optimize visual hierarchy for single-screen storytelling and decision clarity.",
        "hashtags": [
            "#DashboardDesign",
            "#ExecutiveDashboard",
            "#DataVisualization",
            "#DecisionSupport",
            "#BusinessIntelligence",
            "#DataAnalytics",
        ],
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
        if any(token in text for token in ("trade-off", "tradeoff", "trade off")):
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
            hashtags=profile["hashtags"],
            primary_source_url=FEATURED_DASHBOARD_LINK,
            supporting_source_urls=[FEATURED_DASHBOARD_DATA_LINK, FEATURED_DASHBOARD_SCRIPT_LINK, PORTFOLIO_LINK],
            claims=[
                "The flagship repository includes a 2,160-row synthetic retail dataset and portfolio-facing dashboard artifacts.",
                "The project links revenue, margin, retention, returns, fulfillment delay, and stockout indicators in one decision-ready stack.",
                "The objective is to drive business decisions, not visual decoration.",
            ],
            visual_style=profile["visual_style"],
            visual_prompt=profile["visual_prompt"],
            alt_text="Premium insight card comparing growth, margin, retention, and operations health as linked business decisions.",
        )

    def _render_visual(self, draft: DraftPost) -> VisualAsset:
        asset_path = self._visual_path(draft)
        style, variant = self._visual_base_and_variant(draft.visual_style)
        if style == "diagram":
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
        fallback_reason = ""
        fallback_candidate = None
        candidate = None
        citations: list[dict[str, Any]] = []
        trend_report = None
        weekday_index, special_weekday = self._weekday_rotation_state()
        required_bucket = self._required_bucket(weekday_index, special_weekday)
        try:
            candidates, citations = self.research()
        except Exception as exc:
            fallback_reason = str(exc)
            candidates = []
        if not candidates:
            fallback_list = self._fallback_trend_candidates(required_bucket)
            if not fallback_list:
                return self._skip(
                    fallback_reason or "No trend passed ranking and evidence gates.",
                    citations=citations,
                )
            fallback_candidate = self._pick_fallback_candidate(fallback_list)
            candidate = fallback_candidate
        else:
            candidate = candidates[0]
            trend_report = validate_trend(candidate, self.config, self.history)
            if required_bucket and self._candidate_bucket(candidate) != required_bucket:
                fallback_list = self._fallback_trend_candidates(required_bucket)
                if fallback_list:
                    fallback_candidate = self._pick_fallback_candidate(fallback_list)
                    candidate = fallback_candidate
                    trend_report = None
            if trend_report is not None and not trend_report.passed:
                fallback_list = self._fallback_trend_candidates()
                if not fallback_list:
                    return self._skip("; ".join(trend_report.reasons), candidate=candidate, citations=citations)
                fallback_list = self._fallback_trend_candidates(required_bucket)
                if not fallback_list:
                    fallback_list = self._fallback_trend_candidates()
                fallback_candidate = self._pick_fallback_candidate(fallback_list)
                candidate = fallback_candidate
                trend_report = None
        try:
            if fallback_candidate:
                draft = self._fallback_draft(candidate)
                normalize_draft(draft)
                visual = self._render_visual(draft)
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
