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


def render_insight_card(draft: DraftPost, config: AgentConfig, output_path: Path) -> Path:
    """Render a topic-specific editorial visual without generative-image dependencies."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    art = _art_direction(draft)
    image = _paper_background(WORK_CANVAS, art, draft.topic)
    draw = ImageDraw.Draw(image)

    _draw_scene(draw, draft, art)
    _draw_editorial_copy(draw, draft, art)
    _draw_corner_mark(draw, art)

    image.resize((CANVAS, CANVAS), Image.Resampling.LANCZOS).save(output_path, "PNG", optimize=True)
    return output_path


def render_diagram(draft: DraftPost, config: AgentConfig, output_path: Path) -> Path:
    """Render a restrained editorial process diagram with physical depth."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    art = _art_direction(draft)
    image = _paper_background(WORK_CANVAS, art, draft.topic + " diagram")
    draw = ImageDraw.Draw(image)

    _draw_diagram_story(draw, art)
    _draw_editorial_copy(draw, draft, art, compact=True)
    _draw_corner_mark(draw, art)

    image.resize((CANVAS, CANVAS), Image.Resampling.LANCZOS).save(output_path, "PNG", optimize=True)
    return output_path


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


def _art_direction(draft: DraftPost) -> dict[str, str]:
    text = f"{draft.category} {draft.topic}".lower()
    if any(word in text for word in ("bionemo", "drug discovery", "drug-development", "molecular", "life-science", "scientific research")):
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
