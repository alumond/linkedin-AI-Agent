"""Handoff between Codex image generation and the unattended publisher.

The review record is an audit assertion, not automatic visual-quality detection.
Only create it after generating and inspecting the image against the exact draft.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse
from PIL import Image

from .models import DraftPost, VisualAsset, to_dict
from .validators import validate_visual


def visual_signature(path: Path) -> str:
    """Perceptual fingerprint for comparing images, without editing the asset."""
    with Image.open(path) as image:
        pixels = list(image.convert("L").resize((17, 16)).getdata())
    bits = [pixels[y * 17 + x] > pixels[y * 17 + x + 1]
            for y in range(16) for x in range(16)]
    return f"{int(''.join('1' if bit else '0' for bit in bits), 2):064x}"


def draft_sha256(draft: DraftPost) -> str:
    payload = json.dumps(to_dict(draft), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def write_visual_brief(draft: DraftPost, asset_path: Path) -> Path:
    path = asset_path.parent / "briefs" / f"{asset_path.stem}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "draft": to_dict(draft),
        "draft_sha256": draft_sha256(draft),
        "asset": str(asset_path),
        "instructions": (
            "Use an authentic, unchanged screenshot from this project's repository. "
            "Do not generate or redraw the dashboard. Inspect the screenshot against "
            "the exact post, verify the source and original bytes, and save a "
            "project_screenshot review record with source_repository, source_url, "
            "source_blob_sha, source_sha256 and capture_method=repository_asset. "
            "Preserve source data labels and disclose simulated data in the post."
        ) if draft.visual_style == "project_screenshot" else (
            "Generate with Codex imagegen, then visually inspect against this exact post. "
            "Check readable text, correct spelling, meaningful diagrams, topic alignment, "
            "no invented statistics and no internal drafting notes. Save a .json review "
            "record beside the image only after those checks pass. Never use a template "
            "renderer or rename an old image to satisfy this requirement. Compare against "
            "previous artwork: do not repeat its composition with a changed headline or color. "
            "For workflow posts, depict the workflow discussed in the draft, not the process "
            "of creating a LinkedIn post. Check the input, stage order, arrow directions, "
            "decisions, people/tool handoffs, supported revision paths and output against "
            "the text and evidence. Use a process map, decision flow or swimlanes as needed; "
            "do not invent stages or connections, and label proposed workflows as proposed. "
            "No sketches, model drawings, wireframes, stock people, or generic AI artwork."
        ),
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def reviewed_visual(draft: DraftPost, asset_path: Path) -> VisualAsset:
    brief = write_visual_brief(draft, asset_path)
    if not asset_path.exists():
        if draft.visual_style == "project_screenshot":
            raise RuntimeError(f"A reviewed project screenshot is required. Missing: {asset_path}. Brief: {brief}.")
        raise RuntimeError(
            "A Codex-generated topic-specific image is required before posting or dry-running. "
            f"Missing topic image: {asset_path}. Prepare it from {brief}."
        )
    record_path = asset_path.with_suffix(".json")
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Codex image review record is missing or invalid: {record_path}. Brief: {brief}.") from exc
    if not isinstance(record, dict) or (
        record.get("provider") not in {"codex_imagegen", "project_screenshot"}
        or record.get("review_status") != "passed"
        or not record.get("review_notes")
        or not record.get("reviewed_at")
    ):
        raise RuntimeError("Image must have a supported provider and completed visual review record.")
    screenshot = record["provider"] == "project_screenshot"
    if screenshot != (draft.visual_style == "project_screenshot"):
        raise RuntimeError("Image provider does not match the requested visual style.")
    if not screenshot and not record.get("prompt"):
        raise RuntimeError("Codex image must have a completed imagegen provenance and visual review record.")
    if record.get("topic") != draft.topic or record.get("draft_sha256") != draft_sha256(draft):
        raise RuntimeError(f"Codex image was not reviewed against this exact post. Prepare it from {brief}.")
    actual_hash = hashlib.sha256(asset_path.read_bytes()).hexdigest()
    if record.get("asset_sha256") != actual_hash:
        raise RuntimeError("Codex image changed after visual review. Generate or review the replacement before posting.")
    if screenshot:
        repository = record.get("source_repository", "")
        source = record.get("source_url", "")
        parsed = urlparse(repository)
        if (draft.category != "portfolio" or repository != draft.primary_source_url.rstrip("/")
                or parsed.scheme != "https" or parsed.netloc != "github.com"
                or len(parsed.path.strip("/").split("/")) != 2
                or not source.startswith(repository + "/blob/")
                or record.get("capture_method") != "repository_asset"):
            raise RuntimeError("Project screenshot needs a verified source from the post's GitHub repository.")
        data = asset_path.read_bytes()
        blob_sha = hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()
        if record.get("source_sha256") != actual_hash or record.get("source_blob_sha") != blob_sha:
            raise RuntimeError("Project screenshot must match the unchanged original source bytes.")
    with Image.open(asset_path) as image:
        if "A" in image.getbands() and image.getchannel("A").getextrema()[0] < 255:
            raise RuntimeError("LinkedIn artwork needs a fully opaque background. Regenerate the image before review.")
    return validate_visual(asset_path, record.get("alt_text", ""), allow_landscape=True,
                           allow_screenshot=screenshot)
