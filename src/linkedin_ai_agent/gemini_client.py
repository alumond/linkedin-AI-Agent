from __future__ import annotations

import base64
import os
import time
from pathlib import Path
from typing import Any

import requests

from .config import AgentConfig
from .json_utils import parse_json_object
from .models import DraftPost, TrendCandidate, draft_from_dict, trend_from_dict


GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiClient:
    def __init__(self) -> None:
        self.api_key = os.environ.get("GEMINI_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is required.")

    def research(self, config: AgentConfig, recent_topics: list[str]) -> tuple[list[TrendCandidate], list[dict[str, Any]]]:
        prompt = f"""
Find 6 current, high-attention trends in data and artificial intelligence for a broad professional LinkedIn audience.
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
- Prioritize hot topics with a recent trigger: product launch, model release, benchmark result, regulation, enterprise adoption signal, major research paper, infrastructure change, or public company announcement.
- Avoid evergreen explainers unless there is a fresh reason professionals should care this week.

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
        prompt = f"""
Write a LinkedIn post for this source-grounded Data and AI trend.

Topic: {candidate.topic}
Summary: {candidate.summary}
Category: {candidate.category}
Sources:
{sources}

Voice: {config.voice}
Audience: {config.audience}
Length: {config.min_post_chars}-{config.max_post_chars} characters.

Rules:
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
- Include practical implications or actions.
- Include a conversational closing question.
- Use 1 to 3 restrained hashtags.
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

    def generate_illustration(self, config: AgentConfig, draft: DraftPost, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        prompt = (
            f"Create a square 1:1 editorial illustration for LinkedIn. No text in the image. "
            f"Topic: {draft.topic}. Direction: {draft.visual_prompt}. "
            f"Use a polished professional visual style with colors {', '.join(config.brand_colors)}."
        )
        response = self._generate_content(
            config.image_model,
            {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"response_modalities": ["IMAGE"], "image_config": {"aspect_ratio": "1:1"}},
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
            retry_after = response.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                wait_seconds = min(int(retry_after), 30)
            else:
                wait_seconds = min(2**attempt, 30)
            time.sleep(wait_seconds)
        assert last_response is not None
        raise RuntimeError(gemini_error_message(last_response))


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
