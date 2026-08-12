from __future__ import annotations

import base64
import hashlib
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .config import AgentConfig
from .models import DraftPost


CANVAS = 1200
WORK_CANVAS = 2400
SCALE = 1


def render_insight_card(draft: DraftPost, config: AgentConfig, output_path: Path, variant: str = "default") -> Path:
    """Render a dense educational infographic card without generative-image dependencies."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    art = _art_direction(draft, variant=variant)
    image = _infographic_background(WORK_CANVAS, art)
    draw = ImageDraw.Draw(image)

    if variant == "focus_strip":
        _draw_focus_strip_card(draw, draft, art)
    elif variant == "stacked_grid":
        _draw_stacked_grid_card(draw, draft, art)
    elif variant == "editorial":
        _draw_editorial_card(draw, draft, art)
    elif variant == "grid_strategic":
        _draw_grid_strategy_card(draw, draft, art)
    else:
        _draw_infographic_card(draw, draft, art)

    image.resize((CANVAS, CANVAS), Image.Resampling.LANCZOS).save(output_path, "PNG", optimize=True)
    return output_path


def render_diagram(draft: DraftPost, config: AgentConfig, output_path: Path, variant: str = "default") -> Path:
    """Render a diagram-led decision card with a distinct visual grammar from insight cards."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    art = _art_direction(draft, variant=variant)
    image = _infographic_background(WORK_CANVAS, art)
    draw = ImageDraw.Draw(image)

    if variant == "risk_loop":
        _draw_risk_loop_layout(draw, draft, art)
    elif variant == "clarity_tier":
        _draw_clarity_tier_layout(draw, draft, art)
    elif variant == "tradeoff_matrix":
        _draw_tradeoff_matrix_layout(draw, draft, art)
    elif variant == "snapshot_ready":
        _draw_snapshot_layout(draw, draft, art)
    else:
        _draw_diagram_layout(draw, draft, art)

    image.resize((CANVAS, CANVAS), Image.Resampling.LANCZOS).save(output_path, "PNG", optimize=True)
    return output_path


def _draw_diagram_layout(draw: ImageDraw.ImageDraw, draft: DraftPost, art: dict[str, str]) -> None:
    theme = _infographic_theme(draft)
    draw.rounded_rectangle((84, 84, 2316, 2316), radius=52, fill=art["paper"], outline=art["shadow"], width=6)
    _draw_editorial_copy(draw, draft, art, compact=True)
    _draw_diagram_story(draw, art)
    _section_title(draw, str(theme["grid_title"]).upper(), 1728, art)
    _draw_decision_strip(draw, art, theme)
    _draw_takeaway(draw, draft, art, theme)


def _draw_focus_strip_card(draw: ImageDraw.ImageDraw, draft: DraftPost, art: dict[str, str]) -> None:
    theme = _infographic_theme(draft)
    _draw_premium_header(draw, draft, art, theme)
    _premium_section_title(draw, "PRIMARY DECISION", 960, art)
    _draw_decision_strip(draw, art, theme)
    _draw_premium_examples(draw, art, theme)
    _draw_premium_takeaway(draw, draft, art, theme)


def _draw_stacked_grid_card(draw: ImageDraw.ImageDraw, draft: DraftPost, art: dict[str, str]) -> None:
    theme = _infographic_theme(draft)
    _draw_premium_header(draw, draft, art, theme)
    cards = [
        ("REVENUE SIGNAL", "$ +11.6%", "chart"),
        ("MARGIN SIGNAL", "$ +2.1%", "target"),
        ("RETENTION SIGNAL", "82%", "magnify"),
        ("RETURN PRESSURE", "4.8%", "bell"),
    ]
    base_x = 80
    y = 620
    for index, (label, value, icon) in enumerate(cards):
        x = base_x + index * (430)
        _premium_panel(draw, (x, y, x + 404, y + 330), art["paper"], art["accent"] if index % 2 == 0 else "#DDE4ED")
        draw.rounded_rectangle((x + 32, y + 26, x + 142, y + 88), radius=22, fill=art["accent2"])
        draw.text((x + 160, y + 36), label, font=_font(30, bold=True), fill=art["ink"])
        _center_text(draw, (x + 202, y + 178), value, _font(58, bold=True), art["accent"])
        _draw_icon(draw, icon, (x + 202, y + 258), 40, art)
    _draw_premium_takeaway(draw, draft, art, theme)


def _draw_editorial_card(draw: ImageDraw.ImageDraw, draft: DraftPost, art: dict[str, str]) -> None:
    theme = _infographic_theme(draft)
    _draw_premium_header(draw, draft, art, theme)
    _premium_section_title(draw, "EDITORIAL NOTE", 980, art)
    _draw_premium_summary(draw, art, theme)
    _draw_section_grid(draw, draft, art, theme)
    _draw_premium_takeaway(draw, draft, art, theme)


def _draw_grid_strategy_card(draw: ImageDraw.ImageDraw, draft: DraftPost, art: dict[str, str]) -> None:
    theme = _infographic_theme(draft)
    _draw_premium_header(draw, draft, art, theme)
    _section_title(draw, str(theme["grid_title"]).upper(), 1110, art)
    concepts = [
        ("Discover", "source and scope", "magnify"),
        ("Validate", "quality and confidence", "shield"),
        ("Decide", "owner + timeline", "target"),
        ("Measure", "variance + impact", "chart"),
        ("Repeat", "optimize cycle", "network"),
    ]
    x = 80
    y = 1180
    for index, (label, note, icon) in enumerate(concepts):
        _premium_panel(draw, (x + index * 356, y, x + index * 356 + 296, y + 300), art["paper"], "#DDE4ED")
        _draw_icon(draw, icon, (x + index * 356 + 154, y + 95), 36, art)
        draw.text((x + index * 356 + 32, y + 150), label.upper(), font=_font(26, bold=True), fill=art["ink"])
        _draw_wrapped_text(draw, note, (x + index * 356 + 30, y + 184), 236, _font(23, bold=True), art["ink"], line_gap=8, max_lines=2)
    _draw_premium_takeaway(draw, draft, art, theme)


def extract_image_bytes(interaction: object) -> bytes:
    for step in getattr(interaction, "steps", []) or []:
        for block in getattr(step, "content", []) or []:
            inline_data = getattr(block, "inline_data", None) or getattr(block, "inlineData", None)
            if inline_data:
                data = getattr(inline_data, "data", None)
                if isinstance(data, str):
                    return base64.b64decode(data)
                if isinstance(data, bytes):
                    return data
    raise ValueError("Gemini response did not contain image bytes.")


def _draw_infographic_card(draw: ImageDraw.ImageDraw, draft: DraftPost, art: dict[str, str]) -> None:
    theme = _infographic_theme(draft)
    _draw_premium_header(draw, draft, art, theme)
    _draw_premium_summary(draw, art, theme)
    _draw_premium_examples(draw, art, theme)
    _draw_premium_concepts(draw, art, theme)
    _draw_premium_checklist(draw, art, theme)
    _draw_premium_takeaway(draw, draft, art, theme)


def _draw_premium_header(draw: ImageDraw.ImageDraw, draft: DraftPost, art: dict[str, str], theme: dict[str, object]) -> None:
    draw.rectangle((0, 0, WORK_CANVAS, 520), fill=art["ink"])
    draw.rounded_rectangle((86, 72, 430, 138), radius=33, fill=_mix(art["accent"], art["ink"], 0.18))
    draw.text((126, 88), _short_category(draft.category).upper(), font=_font(30, bold=True), fill=art["paper"])

    title_lines = _header_title_lines(str(theme["title"]))
    y = 170 if len(title_lines) == 1 else 156
    max_width = 1510
    for index, line in enumerate(title_lines):
        fill = art["paper"] if index == 0 else art["accent2"]
        _draw_fit_text(draw, (86, y + index * 100), line, max_width, 76, 56, fill, bold=True)
    _draw_wrapped_text(draw, str(theme["subtitle"]), (90, 390), 1320, _font(38, bold=True), _mix(art["paper"], "#FFFFFF", 0.15), line_gap=8, max_lines=2)

    _draw_signal_module(draw, (1710, 86, 2310, 430), art)


def _header_title_lines(title: str) -> list[str]:
    cleaned = " ".join(title.upper().split())
    if ":" in cleaned:
        first, second = cleaned.split(":", 1)
        second = second.strip()
        return [f"{first.strip()}:", second] if second else [f"{first.strip()}:"]
    lines = _wrap(cleaned, 27)
    if len(lines) <= 2:
        return lines
    return [lines[0], " ".join(lines[1:])]


def _draw_fit_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    max_width: int,
    start_size: int,
    min_size: int,
    fill: str,
    bold: bool = False,
) -> None:
    size = start_size
    font = _font(size, bold=bold)
    while size > min_size and draw.textbbox((0, 0), text, font=font)[2] > max_width:
        size -= 2
        font = _font(size, bold=bold)
    draw.text(xy, text, font=font, fill=fill)


def _draw_signal_module(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], art: dict[str, str]) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle((x1, y1, x2, y2), radius=44, fill=_mix(art["paper"], art["ink"], 0.9), outline=_mix(art["paper"], art["ink"], 0.68), width=3)
    draw.text((x1 + 46, y1 + 38), "SIGNAL MAP", font=_font(32, bold=True), fill=art["accent2"])
    chart = (x1 + 70, y1 + 122, x2 - 58, y2 - 54)
    draw.line((chart[0], chart[3], chart[2], chart[3]), fill=art["paper"], width=7)
    draw.line((chart[0], chart[3], chart[0], chart[1]), fill=art["paper"], width=7)
    points = [
        (chart[0] + 34, chart[3] - 34),
        (chart[0] + 130, chart[3] - 82),
        (chart[0] + 232, chart[3] - 64),
        (chart[0] + 334, chart[3] - 142),
        (chart[0] + 438, chart[3] - 206),
    ]
    draw.line(points, fill=art["accent2"], width=11)
    for px, py in points:
        draw.ellipse((px - 15, py - 15, px + 15, py + 15), fill=art["accent"], outline=art["paper"], width=4)


def _draw_premium_summary(draw: ImageDraw.ImageDraw, art: dict[str, str], theme: dict[str, object]) -> None:
    _premium_panel(draw, (80, 590, 1132, 930), art["paper"], "#D8DEE8")
    draw.rectangle((80, 590, 104, 930), fill=art["accent2"])
    draw.rounded_rectangle((904, 664, 1068, 828), radius=42, fill=_mix(art["accent2"], art["paper"], 0.78))
    _draw_icon(draw, str(theme["icon"]), (986, 746), 58, art)
    draw.text((154, 638), str(theme["why_title"]).upper(), font=_font(44, bold=True), fill=art["ink"])
    _draw_wrapped_text(draw, str(theme["why_text"]), (154, 714), 680, _font(36), art["ink"], line_gap=16, max_lines=4)

    _premium_panel(draw, (1200, 590, 2320, 930), art["paper"], _mix(art["accent"], art["paper"], 0.3))
    _draw_clean_target(draw, (1348, 760), 112, art)
    draw.text((1518, 644), "PRACTICAL GOAL", font=_font(40, bold=True), fill=art["accent"])
    draw.text((1518, 706), str(theme["goal"]).upper(), font=_font(54, bold=True), fill=art["ink"])
    draw.text((1522, 778), str(theme["goal_note"]), font=_font(34), fill=_mix(art["ink"], art["paper"], 0.28))
    _draw_mini_steps(draw, (1518, 842), list(theme["criteria"])[:3], art)


def _draw_mini_steps(draw: ImageDraw.ImageDraw, xy: tuple[int, int], items: list[tuple[str, str]], art: dict[str, str]) -> None:
    x, y = xy
    for index, (label, _icon) in enumerate(items):
        left = x + index * 238
        draw.rounded_rectangle((left, y, left + 208, y + 54), radius=27, fill=_mix(art["accent"], art["paper"], 0.82))
        draw.text((left + 22, y + 14), str(label).upper()[:18], font=_font(20, bold=True), fill=art["ink"])


def _draw_premium_examples(draw: ImageDraw.ImageDraw, art: dict[str, str], theme: dict[str, object]) -> None:
    _premium_section_title(draw, "REAL-WORLD EXAMPLES", 1030, art)
    examples = list(theme["examples"])[:5]
    card_w = 420
    gap = 48
    for index, (label, value, icon) in enumerate(examples):
        x = 80 + index * (card_w + gap)
        _premium_panel(draw, (x, 1096, x + card_w, 1386), art["paper"], "#DDE4ED")
        draw.rounded_rectangle((x + 122, 1128, x + 298, 1274), radius=38, fill=_mix(art["accent"], art["paper"], 0.87))
        _draw_icon(draw, icon, (x + 210, 1198), 58, art)
        _center_text(draw, (x + card_w // 2, 1310), str(label), _font(31, bold=True), art["ink"])
        _center_text(draw, (x + card_w // 2, 1354), str(value), _font(31, bold=True), art["accent"])


def _draw_premium_concepts(draw: ImageDraw.ImageDraw, art: dict[str, str], theme: dict[str, object]) -> None:
    _premium_section_title(draw, str(theme["grid_title"]).upper(), 1488, art)
    concepts = list(theme["concepts"])[:3]
    card_w = 720
    gap = 40
    for index, (label, note, best, icon) in enumerate(concepts):
        x = 80 + index * (card_w + gap)
        _premium_panel(draw, (x, 1556, x + card_w, 1878), art["paper"], art["accent"] if index == 0 else "#DDE4ED")
        _draw_icon(draw, icon, (x + 92, 1624), 38, art)
        draw.text((x + 168, 1592), f"0{index + 1}", font=_font(32, bold=True), fill=art["accent"])
        draw.text((x + 168, 1630), str(label).upper(), font=_font(40, bold=True), fill=art["ink"])
        _draw_wrapped_text(draw, str(note), (x + 44, 1702), card_w - 88, _font(30), art["ink"], line_gap=13, max_lines=3)
        draw.rounded_rectangle((x + 44, 1810, x + card_w - 44, 1858), radius=24, fill=_mix(art["accent2"], art["paper"], 0.76))
        draw.text((x + 72, 1823), f"Best for: {best}", font=_font(23, bold=True), fill=art["ink"])


def _draw_premium_checklist(draw: ImageDraw.ImageDraw, art: dict[str, str], theme: dict[str, object]) -> None:
    title = str(theme["choose_title"]).upper()
    draw.text((80, 1942), title, font=_font(38, bold=True), fill=art["accent"])
    items = list(theme["criteria"])[:5]
    x = 80
    for label, _icon in items:
        width = 420
        draw.rounded_rectangle((x, 2008, x + width, 2102), radius=47, fill=art["paper"], outline="#DDE4ED", width=4)
        draw.ellipse((x + 32, 2036, x + 82, 2086), fill=art["accent"], outline=art["ink"], width=4)
        draw.line((x + 45, 2062, x + 57, 2074, x + 74, 2048), fill=art["paper"], width=6)
        _draw_wrapped_text(draw, str(label), (x + 104, 2038), width - 126, _font(28, bold=True), art["ink"], line_gap=6, max_lines=2)
        x += width + 35


def _draw_premium_takeaway(draw: ImageDraw.ImageDraw, draft: DraftPost, art: dict[str, str], theme: dict[str, object]) -> None:
    draw.rectangle((0, 2156, WORK_CANVAS, WORK_CANVAS), fill=art["ink"])
    draw.rounded_rectangle((80, 2220, 438, 2300), radius=40, fill=art["accent2"])
    draw.text((124, 2242), "TAKEAWAY", font=_font(34, bold=True), fill=art["ink"])
    takeaway = _takeaway_text(draft, str(theme["takeaway"]))
    _draw_wrapped_text(draw, takeaway, (500, 2216), 1320, _font(40), art["paper"], line_gap=16, max_lines=3)
    _draw_takeaway_sparkline(draw, (1980, 2230, 2310, 2350), art)


def _draw_takeaway_sparkline(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], art: dict[str, str]) -> None:
    x1, y1, x2, y2 = box
    points = [(x1 + 18, y2 - 16), (x1 + 92, y1 + 72), (x1 + 162, y1 + 92), (x1 + 238, y1 + 30), (x2 - 18, y1 + 8)]
    draw.line(points, fill=art["accent2"], width=13)
    for px, py in points:
        draw.ellipse((px - 15, py - 15, px + 15, py + 15), fill=art["accent"])


def _premium_panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: str, outline: str) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle((x1 + 12, y1 + 16, x2 + 12, y2 + 16), radius=34, fill="#D8DEE7")
    draw.rounded_rectangle(box, radius=34, fill=fill, outline=outline, width=4)


def _premium_section_title(draw: ImageDraw.ImageDraw, title: str, y: int, art: dict[str, str]) -> None:
    draw.line((80, y, 790, y), fill=art["accent"], width=6)
    draw.line((1610, y, 2320, y), fill=art["accent"], width=6)
    _center_text(draw, (1200, y), title, _font(42, bold=True), art["accent"])


def _draw_clean_target(draw: ImageDraw.ImageDraw, center: tuple[int, int], size: int, art: dict[str, str]) -> None:
    x, y = center
    for radius, color in ((size, art["accent"]), (int(size * 0.72), art["paper"]), (int(size * 0.43), art["accent"]), (int(size * 0.16), art["paper"])):
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
    draw.line((x + 36, y - 36, x + 122, y - 122), fill=art["ink"], width=14)
    draw.polygon([(x + 122, y - 122), (x + 104, y - 58), (x + 58, y - 104)], fill=art["ink"])


def _draw_infographic_header(draw: ImageDraw.ImageDraw, draft: DraftPost, art: dict[str, str], theme: dict[str, object]) -> None:
    draw.rectangle((0, 0, WORK_CANVAS, 360), fill=art["ink"])
    for x in range(44, 325, 58):
        for y in range(54, 265, 48):
            digit = "1" if (x + y) % 3 == 0 else "0"
            draw.text((x, y), digit, font=_font(27, bold=True), fill=_mix(art["accent"], art["ink"], 0.45))
    title = str(theme["title"]).upper()
    lines = _wrap(title, 24)[:2]
    y = 78 if len(lines) == 1 else 42
    for index, line in enumerate(lines):
        fill = art["paper"] if index == 0 else art["accent2"]
        _center_text(draw, (1120, y + index * 120), line, _font(88, bold=True), fill)
    subtitle = str(theme["subtitle"])
    _center_text(draw, (1120, 286), subtitle[:92], _font(40, bold=True), art["paper"])
    _draw_header_chart(draw, (2060, 112), art)


def _draw_need_and_goal(draw: ImageDraw.ImageDraw, art: dict[str, str], theme: dict[str, object]) -> None:
    left = (64, 410, 1288, 622)
    right = (1350, 410, 2336, 622)
    _plain_panel(draw, left, 28, art["paper"], _mix(art["accent2"], art["paper"], 0.35), 5)
    _plain_panel(draw, right, 28, art["paper"], _mix(art["accent"], art["paper"], 0.35), 5)
    _draw_icon(draw, str(theme["icon"]), (184, 516), 82, art)
    draw.text((310, 448), str(theme["why_title"]).upper(), font=_font(40, bold=True), fill=art["ink"])
    _draw_wrapped_text(draw, str(theme["why_text"]), (310, 506), 870, _font(31), art["ink"], line_gap=10, max_lines=3)
    _draw_icon(draw, "target", (1480, 516), 86, art)
    draw.text((1602, 448), "GOAL:", font=_font(54, bold=True), fill=art["accent"])
    draw.text((1602, 516), str(theme["goal"]).upper(), font=_font(39, bold=True), fill=art["ink"])
    draw.text((1602, 570), str(theme["goal_note"]), font=_font(31), fill=_mix(art["ink"], art["paper"], 0.28))


def _draw_example_strip(draw: ImageDraw.ImageDraw, art: dict[str, str], theme: dict[str, object]) -> None:
    _section_title(draw, "REAL-WORLD EXAMPLES", 716, art)
    examples = list(theme["examples"])
    x = 64
    for label, value, icon in examples:
        box = (x, 780, x + 410, 1088)
        _plain_panel(draw, box, 22, art["paper"], "#D8DEE8", 4)
        _draw_icon(draw, icon, (x + 205, 880), 88, art)
        _center_text(draw, (x + 205, 1000), label, _font(36, bold=True), art["ink"])
        _center_text(draw, (x + 205, 1052), value, _font(35, bold=True), art["accent"])
        x += 466


def _draw_concept_grid(draw: ImageDraw.ImageDraw, art: dict[str, str], theme: dict[str, object]) -> None:
    _section_title(draw, str(theme["grid_title"]).upper(), 1184, art)
    items = list(theme["concepts"])
    cols = 5
    gap = 20
    left = 64
    card_w = 448
    card_h = 500
    for index, (label, note, best, icon) in enumerate(items[:5]):
        row = index // cols
        col = index % cols
        x1 = left + col * (card_w + gap)
        y1 = 1244 + row * (card_h + 24)
        box = (x1, y1, x1 + card_w, y1 + card_h)
        border = art["accent"] if index % 3 == 0 else "#D8DEE8"
        _plain_panel(draw, box, 18, art["paper"], border, 4)
        _draw_icon(draw, icon, (x1 + card_w // 2, y1 + 92), 64, art)
        _center_text(draw, (x1 + card_w // 2, y1 + 184), label, _font(31, bold=True), art["ink"])
        _draw_wrapped_text(draw, note, (x1 + 34, y1 + 240), card_w - 68, _font(24), art["ink"], line_gap=10, max_lines=4)
        draw.line((x1 + 34, y1 + 390, x1 + card_w - 34, y1 + 390), fill="#D4DAE3", width=3)
        draw.text((x1 + 34, y1 + 422), "Best for:", font=_font(23, bold=True), fill=art["accent"])
        _draw_wrapped_text(draw, best, (x1 + 135, y1 + 422), card_w - 170, _font(22), art["ink"], line_gap=7, max_lines=2)


def _draw_decision_strip(draw: ImageDraw.ImageDraw, art: dict[str, str], theme: dict[str, object]) -> None:
    y = 1936
    _section_title(draw, str(theme["choose_title"]).upper(), y - 60, art)
    items = list(theme["criteria"])
    panel = (64, y, 2336, y + 210)
    _plain_panel(draw, panel, 12, _mix(art["paper"], "#FFFFFF", 0.45), "#CDD6E0", 3)
    slot_w = (2336 - 64) // len(items)
    for index, (label, icon) in enumerate(items):
        x = 64 + index * slot_w
        if index:
            draw.line((x, y + 28, x, y + 182), fill="#C9D1DC", width=3)
        _draw_icon(draw, icon, (x + 80, y + 105), 34, art)
        _draw_wrapped_text(draw, label, (x + 142, y + 78), slot_w - 170, _font(27, bold=True), art["ink"], line_gap=8, max_lines=2)


def _draw_takeaway(draw: ImageDraw.ImageDraw, draft: DraftPost, art: dict[str, str], theme: dict[str, object]) -> None:
    draw.rectangle((0, 2200, WORK_CANVAS, WORK_CANVAS), fill=art["ink"])
    draw.text((96, 2244), "KEY TAKEAWAY", font=_font(42, bold=True), fill=art["accent2"])
    takeaway = _takeaway_text(draft, str(theme["takeaway"]))
    _draw_wrapped_text(draw, takeaway, (480, 2240), 1280, _font(36), art["paper"], line_gap=12, max_lines=3)
    draw.line((1860, 2234, 1860, 2376), fill=_mix(art["paper"], art["ink"], 0.35), width=4)
    _draw_icon(draw, "chart", (2110, 2304), 88, art)


def _section_title(draw: ImageDraw.ImageDraw, title: str, y: int, art: dict[str, str]) -> None:
    draw.line((64, y, 800, y), fill=art["accent"], width=5)
    draw.line((1600, y, 2336, y), fill=art["accent"], width=5)
    _center_text(draw, (1200, y - 2), title, _font(39, bold=True), art["accent"])


def _plain_panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int, fill: str, outline: str, width: int) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle((x1 + 9, y1 + 12, x2 + 9, y2 + 12), radius=radius, fill="#D8DDE5")
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def _draw_header_chart(draw: ImageDraw.ImageDraw, origin: tuple[int, int], art: dict[str, str]) -> None:
    x, y = origin
    draw.line((x, y + 180, x + 250, y + 180), fill=art["paper"], width=8)
    draw.line((x, y + 180, x, y - 20), fill=art["paper"], width=8)
    draw.polygon([(x + 250, y + 180), (x + 222, y + 162), (x + 222, y + 198)], fill=art["paper"])
    draw.polygon([(x, y - 20), (x - 18, y + 10), (x + 18, y + 10)], fill=art["paper"])
    points = [(x + 32, y + 142), (x + 82, y + 116), (x + 132, y + 86), (x + 184, y + 38), (x + 230, y + 18)]
    draw.line(points, fill=art["accent2"], width=10)
    for px, py in points:
        draw.ellipse((px - 11, py - 11, px + 11, py + 11), fill=art["accent"], outline=art["paper"], width=3)


def _draw_icon(draw: ImageDraw.ImageDraw, icon: str, center: tuple[int, int], size: int, art: dict[str, str]) -> None:
    x, y = center
    ink = art["ink"]
    accent = art["accent"]
    accent2 = art["accent2"]
    paper = art["paper"]
    if icon in {"target", "goal"}:
        for r, color in ((size, accent), (int(size * 0.68), paper), (int(size * 0.38), accent), (int(size * 0.14), paper)):
            draw.ellipse((x - r, y - r, x + r, y + r), fill=color)
        draw.line((x + size // 3, y - size // 3, x + size, y - size), fill=ink, width=max(5, size // 10))
        draw.polygon([(x + size, y - size), (x + size - 12, y - size + 40), (x + size - 42, y - size + 12)], fill=ink)
    elif icon == "house":
        draw.polygon([(x - size, y), (x, y - size), (x + size, y), (x + size - 18, y + size), (x - size + 18, y + size)], fill=paper, outline=ink)
        draw.polygon([(x - size - 14, y), (x, y - size - 28), (x + size + 14, y)], fill=accent)
        draw.rectangle((x - 22, y + 20, x + 22, y + size), fill=accent2)
        draw.rectangle((x + 42, y + 22, x + 86, y + 64), fill="#B9DBF0", outline=ink, width=3)
    elif icon == "car":
        draw.rounded_rectangle((x - size, y - 12, x + size, y + size // 2), radius=22, fill=accent2, outline=ink, width=5)
        draw.polygon([(x - 56, y - 12), (x - 22, y - 58), (x + 58, y - 58), (x + 94, y - 12)], fill=paper, outline=ink)
        for wx in (x - 58, x + 62):
            draw.ellipse((wx - 24, y + 28, wx + 24, y + 76), fill=ink)
    elif icon == "box":
        draw.polygon([(x - size, y - 35), (x, y - size), (x + size, y - 35), (x, y + 8)], fill=accent2, outline=ink)
        draw.polygon([(x - size, y - 35), (x, y + 8), (x, y + size), (x - size, y + 20)], fill="#D6913C", outline=ink)
        draw.polygon([(x + size, y - 35), (x, y + 8), (x, y + size), (x + size, y + 20)], fill="#B97128", outline=ink)
    elif icon == "thermo":
        draw.rounded_rectangle((x - 18, y - size, x + 18, y + 36), radius=18, fill=paper, outline=ink, width=5)
        draw.ellipse((x - 46, y + 14, x + 46, y + 106), fill=accent, outline=ink, width=5)
        draw.rounded_rectangle((x - 9, y - size + 22, x + 9, y + 42), radius=9, fill=accent)
    elif icon == "clock":
        draw.ellipse((x - size, y - size, x + size, y + size), fill=paper, outline=ink, width=7)
        draw.line((x, y, x, y - size + 32), fill=ink, width=8)
        draw.line((x, y, x + size // 2, y + 16), fill=ink, width=8)
        for dx in (-size - 16, -size - 36, size + 18):
            draw.line((x + dx, y - 20, x + dx + 36, y - 20), fill=accent, width=6)
    elif icon == "chart":
        draw.line((x - size, y + size, x + size, y + size), fill=ink, width=7)
        draw.line((x - size, y + size, x - size, y - size), fill=ink, width=7)
        pts = [(x - size + 18, y + 48), (x - 34, y + 8), (x + 10, y + 20), (x + 82, y - 58)]
        draw.line(pts, fill=accent, width=9)
        for px, py in pts:
            draw.ellipse((px - 10, py - 10, px + 10, py + 10), fill=accent2)
    elif icon == "shield":
        points = [(x, y - size), (x + size, y - size // 2), (x + size * 3 // 4, y + size // 2), (x, y + size), (x - size * 3 // 4, y + size // 2), (x - size, y - size // 2)]
        draw.polygon(points, fill=paper, outline=accent, width=8)
        draw.line((x - 36, y, x - 4, y + 34, x + 58, y - 42), fill=accent, width=12)
    elif icon == "magnify":
        draw.ellipse((x - size, y - size, x + size // 2, y + size // 2), fill=paper, outline=accent, width=10)
        draw.line((x + size // 3, y + size // 3, x + size, y + size), fill=ink, width=15)
    elif icon == "tree":
        draw.line((x, y - size // 2, x, y + size), fill=ink, width=7)
        for dx, dy in ((-58, -14), (58, -14), (-82, 52), (82, 52)):
            draw.line((x, y + 10, x + dx, y + dy), fill=ink, width=6)
            draw.rounded_rectangle((x + dx - 24, y + dy - 24, x + dx + 24, y + dy + 24), radius=10, fill=accent2, outline=ink, width=4)
        draw.rounded_rectangle((x - 28, y - size - 8, x + 28, y - size + 48), radius=10, fill=accent, outline=ink, width=4)
    elif icon == "network":
        nodes = [(x, y - size), (x - size, y - 12), (x + size, y - 12), (x - 52, y + size), (x + 64, y + size)]
        for a, b in ((0, 1), (0, 2), (1, 3), (2, 4), (3, 4), (1, 4)):
            draw.line((nodes[a][0], nodes[a][1], nodes[b][0], nodes[b][1]), fill=accent, width=5)
        for px, py in nodes:
            draw.ellipse((px - 20, py - 20, px + 20, py + 20), fill=paper, outline=ink, width=5)
    elif icon == "database":
        draw.ellipse((x - size, y - size, x + size, y - size // 3), fill=paper, outline=ink, width=5)
        draw.rectangle((x - size, y - size * 2 // 3, x + size, y + size), fill=paper, outline=ink, width=5)
        for yy in (y - 20, y + 46):
            draw.arc((x - size, yy - 36, x + size, yy + 36), 0, 180, fill=accent, width=5)
    elif icon == "bell":
        draw.arc((x - size, y - size, x + size, y + size), 200, 340, fill=accent, width=13)
        draw.rounded_rectangle((x - 70, y - 42, x + 70, y + 56), radius=38, fill=paper, outline=ink, width=5)
        draw.ellipse((x - 22, y + 58, x + 22, y + 102), fill=accent2, outline=ink, width=4)
    else:
        draw.ellipse((x - size, y - size, x + size, y + size), fill=paper, outline=accent, width=8)
        draw.text((x - size // 2, y - size // 2), "AI", font=_font(size // 2, bold=True), fill=ink)


def _infographic_background(size: int, art: dict[str, str]) -> Image.Image:
    image = Image.new("RGB", (size, size), "#F6F8FB")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 360, size, size), fill="#F6F8FB")
    for y in range(380, size, 180):
        draw.line((0, y, size, y), fill="#EEF2F6", width=2)
    return image


def _draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    xy: tuple[int, int],
    max_width: int,
    font: ImageFont.ImageFont,
    fill: str,
    line_gap: int = 8,
    max_lines: int = 3,
) -> None:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        left, top, right, bottom = draw.textbbox((0, 0), candidate, font=font)
        if current and right - left > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    x, y = xy
    line_height = draw.textbbox((0, 0), "Ag", font=font)[3] + line_gap
    for index, line in enumerate(lines[:max_lines]):
        if index == max_lines - 1 and len(lines) > max_lines:
            while draw.textbbox((0, 0), line + "...", font=font)[2] > max_width and " " in line:
                line = line.rsplit(" ", 1)[0]
            line += "..."
        draw.text((x, y + index * line_height), line, font=font, fill=fill)


def _takeaway_text(draft: DraftPost, fallback: str) -> str:
    if draft.claims:
        return f"{draft.claims[0].rstrip('.')}. Validate the evidence, then choose the practical next step."
    return fallback


def _infographic_theme(draft: DraftPost) -> dict[str, object]:
    text = f"{draft.category} {draft.topic} {draft.visual_prompt}".lower()
    if any(word in text for word in ("regression", "forecast", "prediction", "predictive")):
        return {
            "title": "Regression Models: Predicting Continuous Values",
            "subtitle": "Classification predicts categories. Regression predicts numbers.",
            "why_title": "Why regression matters",
            "why_text": "When the target is a continuous value, models estimate numbers from patterns in data.",
            "goal": "Predict a number",
            "goal_note": "(continuous value)",
            "icon": "chart",
            "examples": [
                ("House Price", "$450k", "house"),
                ("Cab Fare", "$32", "car"),
                ("Sales Forecast", "12.5k units", "box"),
                ("Temperature", "31.4 C", "thermo"),
                ("Delivery Time", "23.6 min", "clock"),
            ],
            "grid_title": "Popular Regression Models",
            "concepts": [
                ("Linear", "Models a linear relationship between features and target.", "simple, interpretable patterns", "chart"),
                ("Ridge", "Adds L2 regularization to reduce overfitting.", "many correlated features", "shield"),
                ("Lasso", "Uses L1 regularization and can remove weak features.", "leaner feature sets", "magnify"),
                ("Decision Tree", "Splits the data into readable decision paths.", "non-linear patterns", "tree"),
                ("Random Forest", "Combines many trees to improve stability.", "robust prediction", "tree"),
                ("Gradient Boosting", "Builds sequential models that correct earlier errors.", "high accuracy on structured data", "chart"),
                ("SVR", "Fits a margin around the best relationship.", "small to medium datasets", "chart"),
                ("Neural Network", "Learns complex non-linear relationships across layers.", "large, high-signal data", "network"),
                ("Baseline", "Simple benchmark before complex modeling.", "sanity checks", "target"),
                ("Validation", "Tests whether performance generalizes.", "trustworthy deployment", "shield"),
            ],
            "choose_title": "Choose the right model based on",
            "criteria": [("Features & target", "chart"), ("Dataset size", "database"), ("Noise & outliers", "bell"), ("Interpretability", "magnify"), ("Prediction accuracy", "target")],
            "takeaway": "There is no single best model. Understand the data, pick the right model, validate well, and iterate.",
        }
    if any(word in text for word in ("governance", "regulation", "responsible", "risk", "safety", "policy")):
        return {
            "title": "AI Governance: From Principles to Enforcement",
            "subtitle": "Good governance turns fast-moving AI into accountable operating practice.",
            "why_title": "Why governance matters",
            "why_text": "AI systems now affect real decisions, so teams need controls that are documented and reviewable.",
            "goal": "Reduce unmanaged risk",
            "goal_note": "(without slowing useful adoption)",
            "icon": "shield",
            "examples": [
                ("Model Reviews", "before launch", "magnify"),
                ("Risk Tiers", "clear owners", "shield"),
                ("Data Checks", "quality gates", "database"),
                ("Incident Logs", "fast response", "bell"),
                ("Audit Trail", "evidence ready", "clock"),
            ],
            "grid_title": "Core Governance Building Blocks",
            "concepts": [
                ("Inventory", "Track where AI is used and who owns it.", "visibility before control", "database"),
                ("Risk Rating", "Classify systems by impact, exposure and uncertainty.", "prioritized reviews", "shield"),
                ("Data Controls", "Check source, consent, quality and drift.", "safer inputs", "database"),
                ("Human Review", "Keep accountable people in consequential decisions.", "target"),
                ("Testing", "Evaluate performance, bias, security and failure modes.", "release gates", "magnify"),
                ("Monitoring", "Watch live systems after deployment.", "early warning", "chart"),
                ("Documentation", "Record decisions, evidence and limitations.", "auditable work", "box"),
                ("Incident Response", "Define escalation paths before problems occur.", "fast action", "bell"),
                ("Vendor Review", "Assess third-party models and tools.", "external risk", "network"),
                ("Training", "Make policy usable for product and business teams.", "consistent practice", "tree"),
            ],
            "choose_title": "Prioritize controls based on",
            "criteria": [("User impact", "target"), ("Data sensitivity", "database"), ("Model autonomy", "network"), ("Legal exposure", "shield"), ("Monitoring ability", "chart")],
            "takeaway": "The strongest AI governance is practical: clear ownership, visible evidence, and review at the right moments.",
        }
    if any(word in text for word in ("dashboard", "revenue", "retention", "kpi", "business intelligence", "profit", "customer", "reporting", "portfolio", "analytics", "growth", "margin", "returns")):
        return {
            "title": _headline_from_topic(draft.topic, "Business Analytics Decision Map"),
            "subtitle": "Useful analytics links performance, pressure, and ownership in one view.",
            "why_title": "Why it matters",
            "why_text": "A metric becomes valuable when it changes a management decision, budget choice, or operating action.",
            "goal": "Move from chart to action",
            "goal_note": "(signal, owner, next step)",
            "icon": "chart",
            "examples": [
                ("Revenue", "quality check", "chart"),
                ("Margin", "pressure view", "target"),
                ("Retention", "repeat signal", "magnify"),
                ("Returns", "leakage watch", "bell"),
                ("Owner", "next action", "shield"),
            ],
            "grid_title": "Decision-Ready Analytics Stack",
            "concepts": [
                ("Business Question", "Define the decision before choosing charts.", "prevents decorative reporting", "target"),
                ("Data Source", "Map where each number comes from.", "trust and traceability", "database"),
                ("KPI Logic", "Connect revenue, profit, retention, and service pressure.", "quality of growth", "chart"),
                ("Variance", "Show what changed against plan or prior period.", "attention control", "bell"),
                ("Owner", "Tie the signal to a person or team.", "clear accountability", "shield"),
                ("Action", "State the next move if the threshold is crossed.", "decision speed", "network"),
                ("Review", "Check if the action improved the metric later.", "learning loop", "clock"),
                ("Evidence", "Keep source links and assumptions visible.", "audit-ready work", "magnify"),
                ("Trade-off", "Expose what worsened while another KPI improved.", "better judgment", "target"),
                ("Portfolio Proof", "Show data, code, output, and thinking together.", "client confidence", "box"),
            ],
            "choose_title": "Judge the dashboard by",
            "criteria": [("Decision clarity", "target"), ("Data quality", "database"), ("Margin impact", "chart"), ("Customer signal", "magnify"), ("Action owner", "shield")],
            "takeaway": "A strong dashboard does not ask people to admire charts. It tells them where to act next.",
        }
    if any(word in text for word in ("governance", "regulation", "responsible", "risk", "safety", "policy")):
        return {
            "title": "AI Governance: From Principles to Enforcement",
            "subtitle": "Good governance turns fast-moving AI into accountable operating practice.",
            "why_title": "Why governance matters",
            "why_text": "AI systems now affect real decisions, so teams need controls that are documented and reviewable.",
            "goal": "Reduce unmanaged risk",
            "goal_note": "(without slowing useful adoption)",
            "icon": "shield",
            "examples": [
                ("Model Reviews", "before launch", "magnify"),
                ("Risk Tiers", "clear owners", "shield"),
                ("Data Checks", "quality gates", "database"),
                ("Incident Logs", "fast response", "bell"),
                ("Audit Trail", "evidence ready", "clock"),
            ],
            "grid_title": "Core Governance Building Blocks",
            "concepts": [
                ("Inventory", "Track where AI is used and who owns it.", "visibility before control", "database"),
                ("Risk Rating", "Classify systems by impact, exposure and uncertainty.", "prioritized reviews", "shield"),
                ("Data Controls", "Check source, consent, quality and drift.", "safer inputs", "database"),
                ("Human Review", "Keep accountable people in consequential decisions.", "target"),
                ("Testing", "Evaluate performance, bias, security and failure modes.", "release gates", "magnify"),
                ("Monitoring", "Watch live systems after deployment.", "early warning", "chart"),
                ("Documentation", "Record decisions, evidence and limitations.", "auditable work", "box"),
                ("Incident Response", "Define escalation paths before problems occur.", "fast action", "bell"),
                ("Vendor Review", "Assess third-party models and tools.", "external risk", "network"),
                ("Training", "Make policy usable for product and business teams.", "consistent practice", "tree"),
            ],
            "choose_title": "Prioritize controls based on",
            "criteria": [("User impact", "target"), ("Data sensitivity", "database"), ("Model autonomy", "network"), ("Legal exposure", "shield"), ("Monitoring ability", "chart")],
            "takeaway": "The strongest AI governance is practical: clear ownership, visible evidence, and review at the right moments.",
        }
    if any(word in text for word in ("ai agent", "ai agents", "agentic", "tool-calling agent")):
        return {
            "title": "AI Agents: From Task to Workflow",
            "subtitle": "Useful agents connect tools, evidence and review into repeatable workflows.",
            "why_title": "Why agents matter",
            "why_text": "Callable tools let an AI system gather context, run steps and hand off decisions with a record.",
            "goal": "Automate repeatable work",
            "goal_note": "(keep judgment accountable)",
            "icon": "network",
            "examples": [
                ("Research", "source scan", "magnify"),
                ("Analysis", "pattern check", "chart"),
                ("Operations", "handoffs", "box"),
                ("Monitoring", "alerts", "bell"),
                ("Review", "human signoff", "target"),
            ],
            "grid_title": "Agent Workflow Components",
            "concepts": [
                ("Trigger", "A clear event starts the workflow.", "bounded entry points", "bell"),
                ("Context", "The agent retrieves the right files, data or sources.", "grounded work", "database"),
                ("Tool Call", "A task is executed through a controlled system.", "repeatable actions", "network"),
                ("Validation", "Outputs are checked against rules or evidence.", "quality gates", "shield"),
                ("Memory", "Relevant history guides what not to repeat.", "continuity", "database"),
                ("Escalation", "Uncertain cases move to a person.", "risk control", "target"),
                ("Logging", "Each action leaves a trace.", "audit readiness", "box"),
                ("Monitoring", "Failures and drift are watched over time.", "stable operation", "chart"),
                ("Permissions", "Access is limited to what the task needs.", "least privilege", "shield"),
                ("Iteration", "Workflow performance improves with review.", "learning loop", "tree"),
            ],
            "choose_title": "Automate only when you understand",
            "criteria": [("Task frequency", "clock"), ("Error cost", "shield"), ("Data access", "database"), ("Review point", "target"), ("Success metric", "chart")],
            "takeaway": "The best agent workflows remove manual handoffs while making accountability easier to see.",
        }
    return {
        "title": _headline_from_topic(draft.topic, "Data and AI Brief"),
        "subtitle": "A practical map of what changed, why it matters, and what to watch next.",
        "why_title": "Why it matters",
        "why_text": "The signal is useful when teams can connect the news to decisions, risks and near-term action.",
        "goal": "Turn signal into action",
        "goal_note": "(with evidence and judgment)",
        "icon": "chart",
        "examples": [
            ("Product Teams", "roadmap input", "box"),
            ("Data Teams", "quality check", "database"),
            ("Executives", "risk view", "target"),
            ("Analysts", "evidence scan", "magnify"),
            ("Operations", "workflow fit", "clock"),
        ],
        "grid_title": "What Professionals Should Check",
        "concepts": [
            ("Trigger", "What changed recently and who announced it?", "fresh context", "bell"),
            ("Evidence", "Which sources support the main claim?", "better judgment", "magnify"),
            ("Use Case", "Where could this help real work?", "practical fit", "target"),
            ("Limits", "What does the evidence not prove yet?", "risk awareness", "shield"),
            ("Data Need", "What inputs would make this reliable?", "quality control", "database"),
            ("Workflow", "Which process would change first?", "adoption path", "network"),
            ("Cost", "What resources or tradeoffs are implied?", "clear decisions", "chart"),
            ("Governance", "Who owns review and accountability?", "safer rollout", "shield"),
            ("Skills", "What should teams learn or update?", "capability building", "tree"),
            ("Next Step", "What small experiment would test value?", "low-risk learning", "target"),
        ],
        "choose_title": "Read the signal through",
        "criteria": [("Evidence quality", "magnify"), ("Business relevance", "target"), ("Data readiness", "database"), ("Risk level", "shield"), ("Actionability", "chart")],
        "takeaway": "Strong AI adoption starts with evidence, clear use cases, and disciplined review.",
    }


def _headline_from_topic(topic: str, fallback: str) -> str:
    cleaned = " ".join(topic.replace(" and ", " & ").split())
    if not cleaned:
        return fallback
    if len(cleaned) <= 58:
        return cleaned
    return cleaned[:55].rsplit(" ", 1)[0] + "..."


def _draw_scene(draw: ImageDraw.ImageDraw, draft: DraftPost, art: dict[str, str]) -> None:
    scene = art["scene"]
    if scene == "lab_workflow":
        _draw_lab_workflow(draw, art)
    elif scene == "pipeline":
        _draw_pipeline(draw, art)
    elif scene == "governance":
        _draw_governance(draw, art)
    elif scene == "research":
        _draw_research(draw, art)
    elif scene == "career":
        _draw_staircase(draw, art)
    elif scene == "business":
        _draw_bridge(draw, art)
    elif scene == "analytics":
        _draw_analytics(draw, art)
    else:
        _draw_launch(draw, art)


def _draw_lab_workflow(draw: ImageDraw.ImageDraw, art: dict[str, str]) -> None:
    """Tell a complete science-agent story from question to human decision."""
    centers = [360, 920, 1480, 2040]
    top = 1060
    card_w = 420
    card_h = 570
    labels = ["RESEARCH QUESTION", "SELECT TOOL", "DIGITAL EXPERIMENT", "SCIENTIST REVIEW"]

    # One continuous path makes the reading order obvious even at feed size.
    path_y = top + 250
    for left, right in zip(centers, centers[1:]):
        _draw_story_arrow(draw, (left + 215, path_y), (right - 215, path_y), art)

    for index, (center, label) in enumerate(zip(centers, labels), start=1):
        x1 = center - card_w // 2
        x2 = center + card_w // 2
        y1 = top
        y2 = top + card_h
        _rounded_block(draw, (x1, y1, x2, y2), 52, art["paper"], art["shadow"])
        draw.rounded_rectangle((x1 + 24, y1 + 24, x1 + 102, y1 + 102), radius=39, fill=art["accent"])
        _center_text(draw, (x1 + 63, y1 + 63), f"{index:02d}", _font(30, bold=True), art["paper"])
        _center_text(draw, (center, y2 + 78), label, _font(35, bold=True), art["ink"])

        if index == 1:
            _draw_question_card(draw, (center, top + 315), art)
        elif index == 2:
            _draw_tool_selector(draw, (center, top + 315), art)
        elif index == 3:
            _draw_digital_experiment(draw, (center, top + 315), art)
        else:
            _draw_scientist_review(draw, (center, top + 315), art)

    # A short caption states the guardrail, which is the post's central judgment.
    caption = "AI RUNS THE COMPUTATION. A SCIENTIST OWNS THE DECISION."
    _center_text(draw, (1200, 1955), caption, _font(44, bold=True), art["ink"])
    draw.line((700, 2020, 1700, 2020), fill=art["accent2"], width=12)


def _draw_story_arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], art: dict[str, str]) -> None:
    x1, y1 = start
    x2, y2 = end
    draw.line((x1 + 14, y1 + 18, x2 + 14, y2 + 18), fill=art["shadow"], width=24)
    draw.line((x1, y1, x2, y2), fill=art["ink"], width=18)
    draw.polygon([(x2, y2), (x2 - 44, y2 - 30), (x2 - 44, y2 + 30)], fill=art["ink"])


def _draw_question_card(draw: ImageDraw.ImageDraw, center: tuple[int, int], art: dict[str, str]) -> None:
    x, y = center
    draw.rounded_rectangle((x - 125, y - 155, x + 125, y + 155), radius=28, fill=art["base"], outline=art["ink"], width=8)
    draw.polygon([(x + 60, y - 155), (x + 125, y - 90), (x + 60, y - 90)], fill=art["accent2"])
    _center_text(draw, (x, y - 22), "?", _font(150, bold=True), art["accent"])
    for px, py in ((x - 92, y + 102), (x, y + 75), (x + 88, y + 108)):
        draw.ellipse((px - 22, py - 22, px + 22, py + 22), fill=art["ink"])
    draw.line((x - 72, y + 96, x - 20, y + 81, x + 65, y + 104), fill=art["ink"], width=9)


def _draw_tool_selector(draw: ImageDraw.ImageDraw, center: tuple[int, int], art: dict[str, str]) -> None:
    x, y = center
    draw.rounded_rectangle((x - 155, y - 132, x + 155, y + 142), radius=42, fill=art["ink"])
    draw.rounded_rectangle((x - 58, y - 190, x + 58, y - 105), radius=28, outline=art["ink"], width=18)
    # Three scientific tools: structure, chemistry and genomics.
    _draw_molecule_icon(draw, (x - 92, y - 5), art["accent2"], art["paper"])
    draw.ellipse((x - 28, y - 55, x + 28, y + 1), outline=art["paper"], width=10)
    draw.line((x, y + 2, x, y + 65), fill=art["paper"], width=10)
    draw.arc((x + 55, y - 70, x + 145, y + 70), 60, 300, fill=art["accent"], width=12)
    draw.arc((x + 55, y - 70, x + 145, y + 70), 240, 480, fill=art["paper"], width=8)
    draw.line((x + 62, y - 48, x + 136, y + 46), fill=art["paper"], width=7)


def _draw_digital_experiment(draw: ImageDraw.ImageDraw, center: tuple[int, int], art: dict[str, str]) -> None:
    x, y = center
    draw.rounded_rectangle((x - 170, y - 150, x + 170, y + 105), radius=30, fill=art["ink"])
    draw.rounded_rectangle((x - 145, y - 125, x + 145, y + 78), radius=18, fill=art["base"])
    _draw_molecule_icon(draw, (x, y - 24), art["accent"], art["ink"])
    draw.polygon([(x - 95, y + 105), (x + 95, y + 105), (x + 150, y + 160), (x - 150, y + 160)], fill=art["accent2"])
    for bx, height in ((-112, 45), (-72, 72), (-32, 105), (8, 78), (48, 124)):
        draw.rounded_rectangle((x + bx, y + 55 - height, x + bx + 20, y + 55), radius=8, fill=art["accent"])


def _draw_scientist_review(draw: ImageDraw.ImageDraw, center: tuple[int, int], art: dict[str, str]) -> None:
    x, y = center
    draw.ellipse((x - 55, y - 170, x + 55, y - 60), fill=art["accent2"])
    draw.pieslice((x - 145, y - 85, x + 145, y + 205), 180, 360, fill=art["ink"])
    draw.rounded_rectangle((x - 65, y - 5, x + 150, y + 175), radius=24, fill=art["paper"], outline=art["accent"], width=10)
    draw.line((x - 15, y + 85, x + 35, y + 130, x + 115, y + 35), fill=art["accent"], width=20, joint="curve")


def _draw_molecule_icon(draw: ImageDraw.ImageDraw, center: tuple[int, int], color: str, line_color: str) -> None:
    x, y = center
    nodes = [(x - 58, y + 25), (x, y - 48), (x + 65, y + 18), (x + 8, y + 65)]
    for a, b in ((0, 1), (1, 2), (2, 3), (3, 0)):
        draw.line((nodes[a][0], nodes[a][1], nodes[b][0], nodes[b][1]), fill=line_color, width=10)
    for px, py in nodes:
        draw.ellipse((px - 23, py - 23, px + 23, py + 23), fill=color, outline=line_color, width=5)


def _draw_launch(draw: ImageDraw.ImageDraw, art: dict[str, str]) -> None:
    # A tactile paper portal and ascending object: a release arriving in the real world.
    cx, cy = _s(1575), _s(1040)
    _soft_ellipse(draw, (cx - _s(560), cy + _s(430), cx + _s(560), cy + _s(590)), art["shadow"])
    for radius, color in ((475, art["ink"]), (375, art["accent"]), (275, art["paper"])):
        draw.ellipse((cx - _s(radius), cy - _s(radius), cx + _s(radius), cy + _s(radius)), fill=color)
    draw.arc((cx - _s(430), cy - _s(430), cx + _s(430), cy + _s(430)), 212, 330, fill=art["highlight"], width=_s(18))
    _draw_capsule(draw, (cx - _s(100), cy - _s(430)), _s(205), _s(600), art["accent2"], art)
    for x, y, radius in ((1120, 430, 34), (2020, 520, 48), (2110, 1370, 25), (1180, 1550, 42)):
        _dimensional_sphere(draw, (_s(x), _s(y)), _s(radius), art["accent"], art["highlight"])


def _draw_pipeline(draw: ImageDraw.ImageDraw, art: dict[str, str]) -> None:
    # A sculptural data route. Curves feel more human than a conventional flowchart.
    points = [(_s(1050), _s(670)), (_s(1420), _s(500)), (_s(1840), _s(760)), (_s(1550), _s(1100)), (_s(1960), _s(1420))]
    shadow_points = [(x + _s(30), y + _s(45)) for x, y in points]
    draw.line(shadow_points, fill=art["shadow"], width=_s(116), joint="curve")
    draw.line(points, fill=art["ink"], width=_s(108), joint="curve")
    draw.line(points, fill=art["accent"], width=_s(72), joint="curve")
    draw.line(points, fill=art["highlight"], width=_s(16), joint="curve")
    for index, (x, y) in enumerate(points):
        color = art["accent2"] if index % 2 else art["paper"]
        _dimensional_sphere(draw, (x, y), _s(96 if index in (0, 4) else 72), color, art["highlight"])
    for x, y, w, h in ((1130, 1200, 230, 320), (1770, 310, 260, 220)):
        _draw_block(draw, (_s(x), _s(y)), _s(w), _s(h), art)


def _draw_governance(draw: ImageDraw.ImageDraw, art: dict[str, str]) -> None:
    # Balance, protection and scrutiny without literal legal clip-art.
    cx = _s(1630)
    base_y = _s(1510)
    _soft_ellipse(draw, (cx - _s(530), base_y, cx + _s(530), base_y + _s(150)), art["shadow"])
    for i, (width, height, color) in enumerate(((760, 170, art["ink"]), (600, 170, art["accent"]), (430, 160, art["accent2"]))):
        y = base_y - _s(180 * (i + 1))
        _rounded_block(draw, (cx - _s(width // 2), y, cx + _s(width // 2), y + _s(height)), _s(46), color, art["shadow"])
    shield = [
        (cx, _s(480)), (cx + _s(290), _s(600)), (cx + _s(230), _s(1000)),
        (cx, _s(1230)), (cx - _s(230), _s(1000)), (cx - _s(290), _s(600)),
    ]
    draw.polygon([(x + _s(28), y + _s(38)) for x, y in shield], fill=art["shadow"])
    draw.polygon(shield, fill=art["paper"], outline=art["ink"])
    draw.line((_s(1500), _s(840), _s(1600), _s(945), _s(1805), _s(700)), fill=art["accent"], width=_s(42), joint="curve")


def _draw_research(draw: ImageDraw.ImageDraw, art: dict[str, str]) -> None:
    # Editorial observatory: evidence under a lens, surrounded by imperfect orbits.
    cx, cy = _s(1600), _s(1000)
    _soft_ellipse(draw, (cx - _s(520), cy + _s(420), cx + _s(520), cy + _s(570)), art["shadow"])
    for radius, width, color, offset in ((470, 16, art["ink"], 0), (360, 26, art["accent"], 38), (245, 14, art["accent2"], 105)):
        box = (cx - _s(radius), cy - _s(radius // 2), cx + _s(radius), cy + _s(radius // 2))
        draw.arc(box, 190 + offset, 510 + offset, fill=color, width=_s(width))
    _dimensional_sphere(draw, (cx, cy), _s(205), art["accent"], art["highlight"])
    draw.ellipse((cx - _s(95), cy - _s(95), cx + _s(95), cy + _s(95)), fill=art["paper"])
    draw.line((cx + _s(120), cy + _s(135), cx + _s(360), cy + _s(370)), fill=art["ink"], width=_s(70))
    for x, y, r in ((1160, 780, 38), (1880, 650, 50), (2050, 1100, 32), (1300, 1320, 44)):
        _dimensional_sphere(draw, (_s(x), _s(y)), _s(r), art["accent2"], art["highlight"])


def _draw_staircase(draw: ImageDraw.ImageDraw, art: dict[str, str]) -> None:
    # A non-corporate staircase with a destination marker for career/tool stories.
    x, y = _s(1090), _s(1530)
    for index in range(5):
        width = _s(245)
        height = _s(155)
        left = x + index * _s(170)
        top = y - index * _s(190)
        _draw_isometric_step(draw, left, top, width, height, art, index)
    _dimensional_sphere(draw, (_s(1910), _s(610)), _s(115), art["accent2"], art["highlight"])
    draw.line((_s(1850), _s(670), _s(1670), _s(930)), fill=art["ink"], width=_s(24))
    for x2, y2 in ((1120, 520), (1280, 760), (2070, 940)):
        draw.line((_s(x2), _s(y2), _s(x2 + 70), _s(y2 - 40)), fill=art["accent"], width=_s(14))


def _draw_bridge(draw: ImageDraw.ImageDraw, art: dict[str, str]) -> None:
    # Two cliffs joined by an optimistic but credible bridge.
    draw.polygon([(_s(980), _s(1050)), (_s(1310), _s(900)), (_s(1430), _s(1780)), (_s(850), _s(1780))], fill=art["ink"])
    draw.polygon([(_s(1830), _s(880)), (_s(2200), _s(1030)), (_s(2280), _s(1780)), (_s(1710), _s(1780))], fill=art["accent2"])
    bridge = [(_s(1240), _s(920)), (_s(1850), _s(850)), (_s(1885), _s(965)), (_s(1280), _s(1035))]
    draw.polygon([(x + _s(24), y + _s(35)) for x, y in bridge], fill=art["shadow"])
    draw.polygon(bridge, fill=art["accent"])
    for x in range(1320, 1830, 115):
        draw.line((_s(x), _s(920), _s(x + 10), _s(1015)), fill=art["highlight"], width=_s(9))
    _dimensional_sphere(draw, (_s(1570), _s(780)), _s(82), art["paper"], art["highlight"])


def _draw_analytics(draw: ImageDraw.ImageDraw, art: dict[str, str]) -> None:
    # Folded ribbons turn a chart into a physical editorial object.
    baseline = _s(1510)
    values = [320, 510, 450, 730, 620]
    points = []
    for i, value in enumerate(values):
        points.append((_s(1050 + i * 250), baseline - _s(value)))
    shadow = [(x + _s(34), y + _s(42)) for x, y in points]
    draw.line(shadow, fill=art["shadow"], width=_s(92), joint="curve")
    draw.line(points, fill=art["accent"], width=_s(78), joint="curve")
    draw.line(points, fill=art["highlight"], width=_s(13), joint="curve")
    for index, point in enumerate(points):
        _dimensional_sphere(draw, point, _s(70), art["accent2"] if index == len(points) - 1 else art["paper"], art["highlight"])
    for y in (620, 900, 1180, 1460):
        draw.line((_s(960), _s(y), _s(2200), _s(y)), fill=_mix(art["ink"], art["base"], 0.82), width=_s(5))


def _draw_diagram_story(draw: ImageDraw.ImageDraw, art: dict[str, str]) -> None:
    centers = [(_s(1120), _s(1180)), (_s(1600), _s(870)), (_s(2070), _s(1180))]
    curve = [centers[0], (_s(1340), _s(850)), centers[1], (_s(1860), _s(850)), centers[2]]
    draw.line([(x + _s(24), y + _s(32)) for x, y in curve], fill=art["shadow"], width=_s(34), joint="curve")
    draw.line(curve, fill=art["ink"], width=_s(25), joint="curve")
    colors = [art["accent2"], art["accent"], art["paper"]]
    symbols = ["01", "02", "03"]
    for center, color, symbol in zip(centers, colors, symbols):
        _dimensional_sphere(draw, center, _s(180), color, art["highlight"])
        font = _font(_s(108), bold=True)
        _center_text(draw, center, symbol, font, art["ink"])
    labels = (("SIGNAL", centers[0]), ("EVIDENCE", centers[1]), ("ACTION", centers[2]))
    for label, (x, y) in labels:
        font = _font(_s(48), bold=True)
        _center_text(draw, (x, y + _s(260)), label, font, art["ink"])


def _draw_risk_loop_layout(draw: ImageDraw.ImageDraw, draft: DraftPost, art: dict[str, str]) -> None:
    theme = _infographic_theme(draft)
    draw.rounded_rectangle((84, 84, 2316, 2316), radius=52, fill=art["paper"], outline=art["shadow"], width=6)
    _draw_editorial_copy(draw, draft, art, compact=True)
    points = [
        (_s(840), _s(1320)),
        (_s(1380), _s(920)),
        (_s(1788), _s(1320)),
        (_s(1380), _s(1760)),
    ]
    for start, end in zip(points, points[1:]):
        draw.line((start[0], start[1], end[0], end[1]), fill=art["ink"], width=14, joint="curve")
    colors = [art["accent"], art["accent2"], art["paper"], art["highlight"]]
    for point, color in zip(points, colors):
        _dimensional_sphere(draw, point, _s(120), color, art["ink"])
        _center_text(draw, point, "RISK", _font(_s(30), bold=True), art["ink"])
    _section_title(draw, "RISK LOOP", 1780, art)
    _draw_decision_strip(draw, art, theme)
    _draw_takeaway(draw, draft, art, theme)


def _draw_clarity_tier_layout(draw: ImageDraw.ImageDraw, draft: DraftPost, art: dict[str, str]) -> None:
    theme = _infographic_theme(draft)
    draw.rounded_rectangle((84, 84, 2316, 2316), radius=52, fill=art["paper"], outline=art["shadow"], width=6)
    _draw_editorial_copy(draw, draft, art, compact=True)
    tiers = [
        ("Signal", art["shadow"], "data signal"),
        ("Diagnosis", art["accent2"], "decision hygiene"),
        ("Action", art["accent"], "owner + timeline"),
    ]
    y = 720
    for index, (title, color, note) in enumerate(tiers):
        x = 190 + index * 760
        _premium_panel(draw, (x, y, x + 650, y + 320), color, art["paper"])
        _draw_wrapped_text(draw, f"{index + 1} • {title}", (x + 40, y + 54), 560, _font(44, bold=True), art["ink"], line_gap=8, max_lines=2)
        _draw_wrapped_text(draw, note, (x + 40, y + 146), 560, _font(32), art["ink"], line_gap=6, max_lines=2)
        _draw_mini_steps(draw, (x + 40, y + 230), [("Owner", "target"), ("Due", "clock"), ("Check", "shield")], art)
    _section_title(draw, "Clarity Ladder", 1170, art)
    _draw_takeaway(draw, draft, art, theme)


def _draw_tradeoff_matrix_layout(draw: ImageDraw.ImageDraw, draft: DraftPost, art: dict[str, str]) -> None:
    theme = _infographic_theme(draft)
    draw.rounded_rectangle((84, 84, 2316, 2316), radius=52, fill=art["paper"], outline=art["shadow"], width=6)
    _draw_editorial_copy(draw, draft, art, compact=True)
    left = _s(260)
    top = _s(720)
    width = _s(920)
    height = _s(760)
    for row in range(2):
        for col in range(2):
            box = (left + col * (width + _s(120)), top + row * (height + _s(140)), left + col * (width + _s(120)) + width, top + row * (height + _s(140)) + height)
            _premium_panel(draw, box, art["paper"], _mix(art["accent"], "#FFFFFF", 0.4))
            title = ["Speed", "Quality", "Cost", "Risk"][row * 2 + col]
            color = [art["accent2"], art["accent"], art["highlight"], art["shadow"]][row * 2 + col]
            draw.text((box[0] + 52, box[1] + 48), title, font=_font(52, bold=True), fill=art["ink"])
            _draw_wrapped_text(
                draw,
                f"Prioritize {title.lower()} where trade-off pressure is highest this week.",
                (box[0] + 52, box[1] + 140),
                width - 104,
                _font(36),
                art["ink"],
                line_gap=12,
                max_lines=4,
            )
            draw.rounded_rectangle((box[0] + 120, box[3] - 120, box[2] - 120, box[3] - 34), radius=22, fill=color)
    _section_title(draw, "Trade-off matrix", 1640, art)
    _draw_takeaway(draw, draft, art, theme)


def _draw_snapshot_layout(draw: ImageDraw.ImageDraw, draft: DraftPost, art: dict[str, str]) -> None:
    theme = _infographic_theme(draft)
    draw.rounded_rectangle((84, 84, 2316, 2316), radius=52, fill=art["paper"], outline=art["shadow"], width=6)
    draw.rectangle((84, 84, 2316, 540), fill=art["ink"])
    draw.rounded_rectangle((142, 138, 560, 206), radius=34, fill=art["accent"])
    draw.text((184, 156), _short_category(draft.category).upper(), font=_font(30, bold=True), fill=art["paper"])

    title_lines = _wrap(draft.topic.upper(), 34)[:3]
    y = 246 if len(title_lines) == 1 else 226
    for index, line in enumerate(title_lines):
        _draw_fit_text(draw, (142, y + index * 78), line, 1560, 64, 46, art["paper"], bold=True)
    _draw_wrapped_text(draw, str(theme["subtitle"]), (154, 454), 1420, _font(32, bold=True), _mix(art["paper"], "#FFFFFF", 0.18), line_gap=6, max_lines=2)
    _draw_signal_module(draw, (1710, 134, 2250, 464), art)

    metrics = [
        ("REVENUE", "+11.6%", "quality checked"),
        ("MARGIN", "+2.1%", "pressure visible"),
        ("RETENTION", "82%", "repeat signal"),
        ("RETURNS", "4.8%", "leakage watch"),
    ]
    for index, (label, value, note) in enumerate(metrics):
        x = 142 + index * 540
        _premium_panel(draw, (x, 650, x + 486, 900), art["paper"], "#D8DEE8")
        draw.text((x + 34, 692), label, font=_font(30, bold=True), fill=art["ink"])
        draw.text((x + 34, 742), value, font=_font(68, bold=True), fill=art["accent"])
        draw.rounded_rectangle((x + 34, 828, x + 420, 868), radius=20, fill=_mix(art["accent2"], art["paper"], 0.72))
        draw.text((x + 54, 836), note.upper(), font=_font(20, bold=True), fill=art["ink"])

    board = (142, 1010, 2258, 1988)
    _premium_panel(draw, board, _mix(art["base"], "#FFFFFF", 0.52), "#D8DEE8")
    draw.text((200, 1070), "EXECUTIVE DECISION VIEW", font=_font(42, bold=True), fill=art["ink"])
    draw.text((200, 1128), "Growth is only credible when profit, retention, returns, and operations agree.", font=_font(31), fill=art["ink"])

    chart = (220, 1230, 1200, 1830)
    draw.line((chart[0], chart[3], chart[2], chart[3]), fill=art["ink"], width=6)
    draw.line((chart[0], chart[3], chart[0], chart[1]), fill=art["ink"], width=6)
    values = [0.38, 0.58, 0.47, 0.72, 0.66, 0.84]
    labels = ["Q1", "Q2", "Q3", "Q4", "Q1", "Q2"]
    bar_w = 86
    gap = 70
    for index, value in enumerate(values):
        x = chart[0] + 90 + index * (bar_w + gap)
        h = int((chart[3] - chart[1] - 70) * value)
        fill = art["accent"] if index in {3, 5} else art["accent2"]
        draw.rounded_rectangle((x, chart[3] - h, x + bar_w, chart[3]), radius=20, fill=fill)
        _center_text(draw, (x + bar_w // 2, chart[3] + 44), labels[index], _font(25, bold=True), art["ink"])
    points = [(chart[0] + 120 + i * 156, chart[3] - int(420 * v) - 72) for i, v in enumerate([0.30, 0.46, 0.42, 0.61, 0.57, 0.78])]
    draw.line(points, fill=art["ink"], width=9)
    for point in points:
        draw.ellipse((point[0] - 13, point[1] - 13, point[0] + 13, point[1] + 13), fill=art["paper"], outline=art["ink"], width=5)

    rows = [
        ("Signal", "Revenue up, margin slower"),
        ("Watch", "Returns and delay pressure"),
        ("Decision", "Protect retention first"),
        ("Owner", "Ops + growth review"),
    ]
    table_x = 1320
    table_y = 1232
    for index, (label, note) in enumerate(rows):
        y1 = table_y + index * 136
        fill = art["paper"] if index % 2 == 0 else _mix(art["accent2"], art["paper"], 0.86)
        draw.rounded_rectangle((table_x, y1, 2160, y1 + 104), radius=28, fill=fill, outline="#D8DEE8", width=3)
        draw.text((table_x + 36, y1 + 30), label.upper(), font=_font(26, bold=True), fill=art["accent"])
        draw.text((table_x + 250, y1 + 30), note, font=_font(30, bold=True), fill=art["ink"])

    _premium_section_title(draw, "SCREENSHOT READY ANALYTICS", 2046, art)
    _draw_premium_takeaway(draw, draft, art, theme)


def _draw_section_grid(draw: ImageDraw.ImageDraw, draft: DraftPost, art: dict[str, str], theme: dict[str, object]) -> None:
    draw.rounded_rectangle((80, 1140, 1520, 1528), radius=42, fill=_mix(art["accent2"], art["paper"], 0.82))
    draw.text((122, 1168), str(theme["why_title"]).upper(), font=_font(38, bold=True), fill=art["ink"])
    _draw_wrapped_text(draw, str(theme["why_text"]), (122, 1236), 1330, _font(40), art["ink"], line_gap=12, max_lines=3)
    _draw_decision_strip(draw, art, theme)


def _draw_editorial_copy(draw: ImageDraw.ImageDraw, draft: DraftPost, art: dict[str, str], compact: bool = False) -> None:
    x = _s(160)
    y = _s(172)
    kicker = _short_category(draft.category).upper()
    kicker_font = _font(_s(40), bold=True)
    title_font = _font(_s(100 if compact else 110), bold=True)
    max_chars = 28 if compact else 18
    max_lines = 2 if compact else 3

    draw.rounded_rectangle((x, y, x + _s(620), y + _s(92)), radius=_s(46), fill=art["accent"])
    draw.text((x + _s(44), y + _s(22)), kicker[:28], font=kicker_font, fill=art["paper"])
    y += _s(168)
    for line in _wrap(draft.topic, max_chars)[:max_lines]:
        draw.text((x, y), line, font=title_font, fill=art["ink"])
        y += _s(124)
    draw.line((x, y + _s(48), x + _s(490), y + _s(48)), fill=art["accent2"], width=_s(18))


def _draw_corner_mark(draw: ImageDraw.ImageDraw, art: dict[str, str]) -> None:
    # A tiny edition mark gives the composition an authored magazine feel.
    x, y = _s(160), _s(2200)
    draw.ellipse((x, y, x + _s(44), y + _s(44)), fill=art["accent"])
    draw.line((x + _s(80), y + _s(22), x + _s(320), y + _s(22)), fill=art["ink"], width=_s(8))


def _paper_background(size: int, art: dict[str, str], seed_text: str) -> Image.Image:
    base = Image.new("RGB", (size, size), art["base"])
    pixels = base.load()
    base_rgb = _hex_to_rgb(art["base"])
    rng = random.Random(int(hashlib.sha256(seed_text.encode("utf-8")).hexdigest()[:16], 16))
    for y in range(size):
        warm_shift = int(7 * y / size)
        for x in range(size):
            vignette = int(10 * math.dist((x, y), (size / 2, size / 2)) / (size * 0.72))
            grain = rng.choice((-2, -1, 0, 0, 0, 1, 2))
            pixels[x, y] = tuple(max(0, min(255, channel - vignette + warm_shift + grain)) for channel in base_rgb)
    return base


def _draw_capsule(draw: ImageDraw.ImageDraw, center: tuple[int, int], width: int, height: int, color: str, art: dict[str, str]) -> None:
    x, y = center
    box = (x - width // 2, y - height // 2, x + width // 2, y + height // 2)
    shadow = tuple(value + (_s(35) if index % 2 == 0 else _s(45)) for index, value in enumerate(box))
    draw.rounded_rectangle(shadow, radius=width // 2, fill=art["shadow"])
    draw.rounded_rectangle(box, radius=width // 2, fill=color)
    draw.arc((x - width // 3, y - height // 2 + _s(25), x + width // 3, y + height // 2 - _s(25)), 98, 260, fill=art["highlight"], width=_s(13))


def _draw_block(draw: ImageDraw.ImageDraw, center: tuple[int, int], width: int, height: int, art: dict[str, str]) -> None:
    x, y = center
    box = (x - width // 2, y - height // 2, x + width // 2, y + height // 2)
    _rounded_block(draw, box, _s(32), art["paper"], art["shadow"])
    for offset in (-55, 0, 55):
        draw.line((x - width // 3, y + _s(offset), x + width // 3, y + _s(offset)), fill=art["accent"], width=_s(10))


def _rounded_block(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], radius: int, color: str, shadow: str) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle((x1 + _s(28), y1 + _s(36), x2 + _s(28), y2 + _s(36)), radius=radius, fill=shadow)
    draw.rounded_rectangle(box, radius=radius, fill=color)


def _draw_isometric_step(draw: ImageDraw.ImageDraw, x: int, y: int, width: int, height: int, art: dict[str, str], index: int) -> None:
    depth = _s(70)
    top = [(x, y), (x + width, y), (x + width + depth, y - depth), (x + depth, y - depth)]
    front = [(x, y), (x + width, y), (x + width, y + height), (x, y + height)]
    side = [(x + width, y), (x + width + depth, y - depth), (x + width + depth, y + height - depth), (x + width, y + height)]
    draw.polygon([(px + _s(24), py + _s(34)) for px, py in front], fill=art["shadow"])
    draw.polygon(front, fill=art["ink"] if index % 2 == 0 else art["accent"])
    draw.polygon(side, fill=_mix(art["accent"], art["ink"], 0.5))
    draw.polygon(top, fill=art["paper"] if index % 2 == 0 else art["accent2"])


def _dimensional_sphere(draw: ImageDraw.ImageDraw, center: tuple[int, int], radius: int, color: str, highlight: str) -> None:
    x, y = center
    draw.ellipse((x - radius + _s(24), y - radius + _s(32), x + radius + _s(24), y + radius + _s(32)), fill="#B8B0A5")
    steps = max(8, radius // 10)
    for i in range(steps, 0, -1):
        ratio = i / steps
        fill = _mix(_mix(color, "#000000", 0.28), color, ratio)
        r = int(radius * ratio)
        draw.ellipse((x - r, y - r, x + r, y + r), fill=fill)
    hr = max(_s(10), radius // 4)
    draw.ellipse((x - radius // 2 - hr, y - radius // 2 - hr, x - radius // 2 + hr, y - radius // 2 + hr), fill=highlight)


def _soft_ellipse(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], color: str) -> None:
    draw.ellipse(box, fill=color)


def _art_direction(draft: DraftPost, variant: str = "default") -> dict[str, str]:
    text = f"{draft.category} {draft.topic}".lower()
    if variant == "focus_strip":
        scene = "analytics"
    elif variant == "stacked_grid":
        scene = "pipeline"
    elif variant in {"editorial", "grid_strategic"}:
        scene = "research"
    elif variant in {"decision_grid", "snapshot_ready"}:
        scene = "business"
    elif variant in {"risk_loop", "clarity_tier", "tradeoff_matrix"}:
        scene = "governance"
    elif any(word in text for word in ("bionemo", "drug discovery", "drug-development", "molecular", "life-science", "scientific research")):
        scene = "lab_workflow"
    elif any(word in text for word in ("data engineering", "database", "pipeline", "warehouse", "cloud", "infrastructure")):
        scene = "pipeline"
    elif any(word in text for word in ("responsible", "safety", "regulation", "governance", "policy", "privacy", "risk")):
        scene = "governance"
    elif any(word in text for word in ("research", "paper", "study", "benchmark", "science")):
        scene = "research"
    elif any(word in text for word in ("career", "job", "skill", "learning", "workforce")):
        scene = "career"
    elif any(word in text for word in ("business", "enterprise", "company", "market", "economy")):
        scene = "business"
    elif any(word in text for word in ("analytics", "metric", "forecast", "insight")):
        scene = "analytics"
    else:
        scene = "launch"

    palettes = [
        {"base": "#F2EBDD", "paper": "#FFF9EE", "ink": "#182C2A", "accent": "#E2573E", "accent2": "#E3B23C", "highlight": "#FFFDF7", "shadow": "#C9BDA8"},
        {"base": "#E8E7E1", "paper": "#FAF9F4", "ink": "#17213A", "accent": "#3454D1", "accent2": "#E56B6F", "highlight": "#FFFFFF", "shadow": "#BEC0C5"},
        {"base": "#E4EEE6", "paper": "#F8F4E8", "ink": "#16302B", "accent": "#DB6B43", "accent2": "#76A88C", "highlight": "#FFFDF4", "shadow": "#B7C7BA"},
        {"base": "#EEE6F0", "paper": "#FFF8ED", "ink": "#2F2342", "accent": "#8756A6", "accent2": "#F19C79", "highlight": "#FFFFFF", "shadow": "#C6B8C9"},
        {"base": "#E8EDF1", "paper": "#FBF7EC", "ink": "#17324D", "accent": "#2D7A78", "accent2": "#D89B45", "highlight": "#FFFFFF", "shadow": "#BCC8CE"},
    ]
    if scene in {"business", "analytics"}:
        result = {"base": "#E8EDF1", "paper": "#FBF7EC", "ink": "#17324D", "accent": "#2D7A78", "accent2": "#D89B45", "highlight": "#FFFFFF", "shadow": "#BCC8CE"}
        result["scene"] = scene
        return result
    index = int(hashlib.sha256(draft.topic.encode("utf-8")).hexdigest(), 16) % len(palettes)
    result = dict(palettes[index])
    result["scene"] = scene
    return result


def _short_category(category: str) -> str:
    cleaned = category.replace("|", " / ").strip()
    return cleaned[:28] if cleaned else "Current signal"


def _center_text(draw: ImageDraw.ImageDraw, center: tuple[int, int], text: str, font: ImageFont.ImageFont, fill: str) -> None:
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    x, y = center
    draw.text((x - (right - left) / 2, y - (bottom - top) / 2 - top), text, font=font, fill=fill)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    paths = (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    )
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap(text: str, max_chars: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        if current and sum(len(item) for item in current) + len(current) + len(word) > max_chars:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines


def _mix(a: str, b: str, t: float) -> str:
    ar, ag, ab = _hex_to_rgb(a)
    br, bg, bb = _hex_to_rgb(b)
    return f"#{int(ar + (br - ar) * t):02X}{int(ag + (bg - ag) * t):02X}{int(ab + (bb - ab) * t):02X}"


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.lstrip("#")
    if len(value) == 8:
        value = value[:6]
    return int(value[:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _s(value: int) -> int:
    return value * SCALE
