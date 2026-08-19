from __future__ import annotations

import base64
import json
import math
import os
import re
import time
from pathlib import Path
from typing import Any

import requests

from .config import AgentConfig
from .json_utils import parse_json_object
from .models import DraftPost, TrendCandidate, draft_from_dict, to_dict, trend_from_dict


GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
MAX_RETRY_DELAY_SECONDS = 60


class GeminiClient:
    def __init__(self) -> None:
        self.api_key = os.environ.get("GEMINI_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is required.")

    def research(self, config: AgentConfig, recent_topics: list[str]) -> tuple[list[TrendCandidate], list[dict[str, Any]]]:
        prompt = f"""
Find 6 current, high-attention topics that build Almond's personal brand as a data analyst for business growth, KPI reporting, dashboards, business intelligence, impact analytics, and AI-assisted decision support.
Use a "discussion-first" style and prioritize topics that can spark useful debate and practical action for recruiters, founders, operators, analytics managers, remote teams, and business leaders.
Use Google Search grounding. Do not scrape LinkedIn.

Editorial topics: {", ".join(config.editorial_topics)}
Excluded subjects: {", ".join(config.excluded_subjects)}
Recently covered topics to avoid: {", ".join(recent_topics) or "none"}
Preferred source domains: {", ".join(config.preferred_source_domains) or "official AI/data sources and credible business/technology reporting"}

Hard evidence requirements for every candidate:
- Include at least one primary source from an official vendor, standards body, research publisher, academic source, government/multilateral source, or original paper.
- Include at least one independent credible source.
- Prefer the configured preferred source domains before using any other source.
- Avoid trend-list blogs, Medium posts, marketing listicles, SEO consulting pages, and Wikipedia as primary evidence.
- Do not use "agentic AI adoption is rising" as the topic unless there is a specific new report, product release, benchmark, standard, or research finding.
- Do not select abstract AI news unless it can be turned into a practical lesson about dashboards, KPI quality, reporting, growth analytics, decision support, data cleaning, portfolio proof, or business performance.
- Prioritize hot topics with a recent trigger: product launch, model release, benchmark result, regulation, enterprise adoption signal, major research paper, infrastructure change, or public company announcement.
- Prioritize topics with strong engagement value:
  - a counterintuitive outcome or correction of a common belief
  - a real operational trade-off executives must decide on
  - a measurable business lever (revenue, retention, cost, speed, risk, talent)
  - a decision framework that can be copied quickly
- Prefer content angles that make Almond look hireable or client-ready:
  - how to turn messy data into clear decisions
  - why dashboards fail when KPIs have no owner
  - how GitHub projects can prove analytics skill
  - what data analysts should show instead of listing tools
  - how teams can use AI to reduce reporting waste
  - how impact data and business analytics connect
- Avoid evergreen explainers unless there is a fresh reason professionals should care this week.
- Prefer developments that touch business outcomes: growth velocity, operating efficiency, pricing power, risk reduction, hiring productivity, or decision quality.
- Favour concrete hooks, unexpected shifts, and practical implications over generic technical updates.

Return only JSON with this shape:
{{
  "candidates": [
    {{
      "topic": "...",
      "category": "AI releases|research|data engineering|analytics|tools|business|careers|explainer|responsible AI",
      "summary": "...",
      "recency_score": 0.0,
      "relevance_score": 0.0,
      "evidence_score": 0.0,
      "practical_value_score": 0.0,
      "novelty_score": 0.0,
      "sources": [
        {{
          "title": "...",
          "url": "https://...",
          "publisher": "...",
          "source_type": "primary|independent",
          "published_at": "YYYY-MM-DD or null",
          "claim_supported": "...",
          "quality_score": 0.0
        }}
      ]
    }}
  ]
}}
"""
        try:
            interaction = self._interactions(config.text_model, prompt, tools=[{"type": "google_search"}])
            text = output_text_from_interaction(interaction)
            citations = extract_citations(interaction)
        except RuntimeError as exc:
            if "timed out" not in str(exc).lower():
                raise
            response = self._generate_content(
                config.text_model,
                {"contents": [{"parts": [{"text": prompt + "\nUse your general knowledge if search is unavailable, but include only high-confidence source URLs you know."}]}], "generationConfig": {"response_mime_type": "application/json"}},
            )
            text = output_text_from_generate_content(response)
            citations = []
        data = parse_json_object(text)
        return [trend_from_dict(item) for item in data.get("candidates", [])], citations

    def generate_post(self, config: AgentConfig, candidate: TrendCandidate) -> DraftPost:
        sources = "\n".join(f"- {source.title}: {source.url} ({source.source_type})" for source in candidate.sources)
        target_min, target_max = post_length_target(config)
        prompt = f"""
Write a LinkedIn post that builds Almond's personal brand as a data analyst for business growth, dashboards, KPI reporting, business intelligence, impact analytics, and decision support.

Topic: {candidate.topic}
Summary: {candidate.summary}
Category: {candidate.category}
Sources:
{sources}

Voice: {config.voice}
Audience: {config.audience}
Hard length limit for body: {config.min_post_chars}-{config.max_post_chars} characters.
Aim for {target_min}-{target_max} body characters so the final draft stays safely inside the hard limit.

Rules:
- Follow the style variant "Hook -> Contrarian angle -> Practical move -> memorable closing".
- Format for LinkedIn native readability: short paragraphs, clear section labels in uppercase, hyphen bullets where useful, and generous spacing.
- Do not use Markdown bold or italics because LinkedIn API posts show the asterisks/underscores as plain text.
- Use section labels such as "WHY THIS MATTERS:", "THE COMMON MISTAKE:", "BETTER MOVE:", "MY TAKE:", or "PRACTICAL RULE:" when they fit naturally.
- Open with a concrete anchor: a decision, metric, or change that changes outcomes.
- Build immediate reader relevance by stating one practical implication in plain language by the second third of the post.
- Make the post sound like it came from a practical data analyst who understands business decisions, not a generic AI news page.
- Tie the topic back to at least one of these lanes: dashboards, KPIs, SQL/Python/Power BI, business growth, reporting automation, data cleaning, impact analytics, GitHub portfolio proof, remote data work, or decision support.
- Include one line that shows judgment, such as what teams should stop doing, measure differently, or prove with data.
- Include one short, light analogy or framing that makes the point memorable without sounding gimmicky.
- End with a catchy closing phrase, sharp takeaway, or memorable final line.
- Do not force questions at the end unless the post genuinely needs one.
- Do not claim personal hands-on testing.
- Do not fabricate quotes or statistics.
- Do not use vague quantified claims like "significant percentage", "many companies", or "most leaders" unless an exact sourced number is provided.
- Never use these words or phrases: delve, foster, leverage, utilize, facilitate, empower, streamline, robust, cutting-edge, paradigm shift, game changer, transformative, supercharge, harness, ever-evolving, "this is huge", "this changes everything", "landscape is shifting", "buzzword", "what's exciting", "are you ready", "powerful capabilities", "new era".
- Start with the concrete development, finding, or consequence. Do not use throat-clearing such as "here's the thing", "let me be clear", or "in today's world".
- Avoid fake insight setups such as "what most people miss" and "here's what nobody tells you".
- Avoid binary contrast formulas such as "this isn't X, it's Y" and "not just X but Y".
- Avoid dramatic fragments, rhetorical questions followed by their answers, fake-profound endings, and summary-recap endings.
- Do not use em dashes. Do not add emojis.
- Name the source when attributing a finding. Never write "experts agree", "studies show", or "industry reports suggest" without naming the source.
- Write like a sharp human analyst: concrete, restrained, useful, and specific.
- Vary sentence length naturally. Prefer active voice and plain verbs.
- Include practical implications or actions readers can use in meetings, planning, or reporting.
- Include a strong final phrase or practical takeaway that makes the post feel complete.
- Use 6 to 10 specific, topic-relevant hashtags.
- For visual_style, use only "insight_card" or "diagram".
- Return only JSON matching this shape:
{{
  "topic": "...",
  "category": "...",
  "body": "...",
  "hashtags": ["#Data", "#AI"],
  "primary_source_url": "https://...",
  "supporting_source_urls": ["https://..."],
  "claims": ["..."],
  "visual_style": "insight_card|diagram",
  "visual_prompt": "...",
  "alt_text": "..."
}}
"""
        response = self._generate_content(
            config.text_model,
            {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"response_mime_type": "application/json"}},
        )
        return draft_from_dict(parse_json_object(output_text_from_generate_content(response)))

    def revise_post(
        self,
        config: AgentConfig,
        candidate: TrendCandidate,
        draft: DraftPost,
        validation_reasons: list[str],
    ) -> DraftPost:
        target_min, target_max = post_length_target(config)
        prompt = f"""
Revise this source-grounded LinkedIn draft so it passes every listed validation issue.

Topic: {candidate.topic}
Validation issues:
{chr(10).join(f"- {reason}" for reason in validation_reasons)}

Current draft JSON:
{json.dumps(to_dict(draft), ensure_ascii=False)}

Requirements:
- Preserve the topic, factual meaning, source URLs, claims, visual direction, and honest point of view.
- Do not add facts, quotations, statistics, source URLs, or personal testing claims.
- Keep the body between {config.min_post_chars} and {config.max_post_chars} characters.
- Aim for {target_min}-{target_max} body characters.
- Retain an attention-first opening line, a practical implication, a strong closing phrase, and 6 to 10 topic-relevant hashtags.
- Do not force a "Discussion prompts:" section unless it already fits naturally.
- Do not use em dashes, emojis, hype, clickbait, or generic AI phrasing.
- Return only the complete revised JSON object using exactly the same fields as the current draft.
"""
        response = self._generate_content(
            config.text_model,
            {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"response_mime_type": "application/json"}},
        )
        return draft_from_dict(parse_json_object(output_text_from_generate_content(response)))

    def generate_illustration(self, config: AgentConfig, draft: DraftPost, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        prompt = (
            "Create a premium LinkedIn infographic for a data and analytics post. "
            "The image must explain the actual argument of the post clearly to an average reader, not just symbolize it. "
            "Use a clean light-background workflow/explainer style with a strong title, numbered cards or clearly separated sections, simple icons, arrows where movement matters, short readable captions, and a concise takeaway area. "
            "Choose square or landscape format depending on what best fits the concept. "
            "Make it feel like a polished executive briefing infographic: clear, calm, commercially aware, and easy to scan in seconds. "
            "All text must be correctly spelled, large enough to read, and directly tied to the post. "
            "Do not include logos, watermarks, generic office stock photography, unlabeled abstract metaphors, dark 3D scenes by default, robot faces, circuit-board cliches, or tiny unreadable UI text. "
            f"Topic: {draft.topic}. "
            f"Post body to interpret visually: {draft.body[:1200]} "
            f"Visual direction: {draft.visual_prompt}. "
            f"Use colors that quietly align with {', '.join(config.brand_colors)} without making the image look like a template."
        )
        response = self._generate_content(
            config.image_model,
            {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"response_modalities": ["IMAGE"]},
            },
        )
        output_path.write_bytes(image_bytes_from_generate_content(response))
        return output_path

    def _interactions(self, model: str, prompt: str, tools: list[dict[str, Any]]) -> dict[str, Any]:
        return self._post_json(
            f"{GEMINI_API_BASE}/interactions",
            {"model": model, "input": prompt, "tools": tools},
            timeout=120,
        )

    def _generate_content(self, model: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post_json(
            f"{GEMINI_API_BASE}/models/{model}:generateContent",
            payload,
            timeout=180,
        )

    def _post_json(self, url: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
        retryable = {408, 429, 500, 502, 503, 504}
        last_response: requests.Response | None = None
        for attempt in range(4):
            try:
                response = requests.post(
                    url,
                    headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
                    json=payload,
                    timeout=timeout,
                )
            except (requests.Timeout, requests.ConnectionError) as exc:
                if attempt == 3:
                    raise RuntimeError(f"Gemini API request timed out or failed to connect after retries: {exc}") from exc
                time.sleep(min(2**attempt, 30))
                continue
            if response.ok:
                return response.json()
            last_response = response
            if response.status_code not in retryable:
                break
            if attempt == 3:
                break
            wait_seconds = gemini_retry_delay(response, fallback_seconds=min(2**attempt, 30))
            time.sleep(wait_seconds)
        assert last_response is not None
        raise RuntimeError(gemini_error_message(last_response))


def post_length_target(config: AgentConfig) -> tuple[int, int]:
    """Return a comfortable target range inside the configured hard limits."""
    target_min = min(config.max_post_chars, config.min_post_chars + 200)
    target_max = max(target_min, config.max_post_chars - 150)
    return target_min, target_max


def gemini_retry_delay(response: requests.Response, fallback_seconds: int) -> int:
    """Read Gemini's requested cooldown, with a bounded exponential fallback."""
    retry_after = response.headers.get("Retry-After", "").strip()
    parsed = float(retry_after) if re.fullmatch(r"\d+(?:\.\d+)?", retry_after) else parse_delay_seconds(retry_after)
    if parsed is None:
        try:
            payload = response.json()
        except (ValueError, TypeError):
            payload = None
        parsed = find_retry_delay(payload)
    if parsed is None:
        parsed = parse_delay_seconds(getattr(response, "text", ""))
    delay = fallback_seconds if parsed is None else max(parsed, 0.0)
    return max(1, min(math.ceil(delay), MAX_RETRY_DELAY_SECONDS))


def find_retry_delay(value: Any) -> float | None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"retryDelay", "retry_delay"}:
                parsed = parse_delay_seconds(str(item))
                if parsed is not None:
                    return parsed
            found = find_retry_delay(item)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = find_retry_delay(item)
            if found is not None:
                return found
    elif isinstance(value, str):
        return parse_delay_seconds(value)
    return None


def parse_delay_seconds(value: str) -> float | None:
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*s(?:ec(?:ond)?s?)?\s*", value, re.IGNORECASE)
    if not match:
        match = re.search(r"retry(?:ing)?\s+in\s+(\d+(?:\.\d+)?)\s*s(?:ec(?:ond)?s?)?\b", value, re.IGNORECASE)
    return float(match.group(1)) if match else None


def output_text_from_interaction(interaction: Any) -> str:
    if isinstance(interaction, dict) and interaction.get("output_text"):
        return str(interaction["output_text"])
    for step in interaction_steps(interaction):
        if not isinstance(step, dict) or step.get("type") != "model_output":
            continue
        for block in step.get("content", []):
            if isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
                return str(block["text"])
    if isinstance(interaction, dict):
        candidates = interaction.get("candidates", [])
        if candidates:
            return output_text_from_generate_content(interaction)
    raise ValueError("Gemini interaction response did not contain text output.")


def output_text_from_generate_content(response: Any) -> str:
    if not isinstance(response, dict):
        raise ValueError("Gemini generateContent response was not a JSON object.")
    candidates = response.get("candidates", [])
    if not candidates or not isinstance(candidates[0], dict):
        raise ValueError("Gemini generateContent response did not contain candidates.")
    parts = candidates[0].get("content", {}).get("parts", [])
    texts = [part.get("text", "") for part in parts if isinstance(part, dict) and part.get("text")]
    if not texts:
        raise ValueError("Gemini generateContent response did not contain text.")
    return "\n".join(texts)


def image_bytes_from_generate_content(response: Any) -> bytes:
    if not isinstance(response, dict):
        raise ValueError("Gemini image response was not a JSON object.")
    candidates = response.get("candidates", [])
    if not candidates or not isinstance(candidates[0], dict):
        raise ValueError("Gemini image response did not contain candidates.")
    parts = candidates[0].get("content", {}).get("parts", [])
    for part in parts:
        if not isinstance(part, dict):
            continue
        inline_data = part.get("inlineData") or part.get("inline_data")
        if inline_data and inline_data.get("data"):
            return base64.b64decode(inline_data["data"])
    raise ValueError("Gemini image response did not contain image bytes.")


def extract_citations(interaction: Any) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    for step in interaction_steps(interaction):
        if not isinstance(step, dict) or step.get("type") != "model_output":
            continue
        for block in step.get("content", []):
            if not isinstance(block, dict):
                continue
            for annotation in block.get("annotations", []) or []:
                if isinstance(annotation, dict) and annotation.get("type") == "url_citation":
                    citations.append(
                        {
                            "title": annotation.get("title", ""),
                            "url": annotation.get("url", ""),
                            "start_index": annotation.get("start_index"),
                            "end_index": annotation.get("end_index"),
                        }
                    )
    return citations


def interaction_steps(interaction: Any) -> list[Any]:
    if isinstance(interaction, dict):
        steps = interaction.get("steps", [])
        return steps if isinstance(steps, list) else []
    if isinstance(interaction, list):
        return interaction
    return []


def gemini_error_message(response: requests.Response) -> str:
    detail = response.text[:1000]
    try:
        data = response.json()
        if isinstance(data, dict):
            error = data.get("error", {})
            if isinstance(error, dict):
                detail = error.get("message", detail)
            else:
                detail = str(error)
        elif isinstance(data, list):
            detail = str(data[:3])
    except ValueError:
        pass
    if response.status_code == 429:
        return (
            "Gemini API returned 429 Too Many Requests. This usually means rate limit or quota exhaustion. "
            f"Details: {detail}"
        )
    return f"Gemini API request failed with HTTP {response.status_code}. Details: {detail}"
