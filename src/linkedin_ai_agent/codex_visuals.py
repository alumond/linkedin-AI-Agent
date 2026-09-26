"""Handoff between Codex image generation and the unattended publisher.

The review record is an audit assertion, not automatic visual-quality detection.
Only create it after generating and inspecting the image against the exact draft.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
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
        record.get("provider") != "codex_imagegen"
        or record.get("review_status") != "passed"
        or not record.get("prompt")
        or not record.get("review_notes")
        or not record.get("reviewed_at")
    ):
        raise RuntimeError("Codex image must have a completed imagegen provenance and visual review record.")
    if record.get("topic") != draft.topic or record.get("draft_sha256") != draft_sha256(draft):
        raise RuntimeError(f"Codex image was not reviewed against this exact post. Prepare it from {brief}.")
    actual_hash = hashlib.sha256(asset_path.read_bytes()).hexdigest()
    if record.get("asset_sha256") != actual_hash:
        raise RuntimeError("Codex image changed after visual review. Generate or review the replacement before posting.")
    with Image.open(asset_path) as image:
        if "A" in image.getbands() and image.getchannel("A").getextrema()[0] < 255:
            raise RuntimeError("LinkedIn artwork needs a fully opaque background. Regenerate the image before review.")
    return validate_visual(asset_path, record.get("alt_text", ""), allow_landscape=True)
