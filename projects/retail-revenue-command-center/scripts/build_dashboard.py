from __future__ import annotations

import csv
import html
import json
import math
from collections import defaultdict
from pathlib import Path
from string import Template
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "outputs"
DATA_PATH = DATA_DIR / "retail_operations_kpis.csv"
SUMMARY_PATH = OUTPUT_DIR / "kpi_summary.json"
DASHBOARD_PATH = OUTPUT_DIR / "dashboard.html"
LANDSCAPE_PATH = OUTPUT_DIR / "linkedin_landscape.html"


MONTHS = [
    "2025-01",
    "2025-02",
    "2025-03",
    "2025-04",
    "2025-05",
    "2025-06",
    "2025-07",
    "2025-08",
    "2025-09",
    "2025-10",
    "2025-11",
    "2025-12",
    "2026-01",
    "2026-02",
    "2026-03",
    "2026-04",
    "2026-05",
    "2026-06",
]

REGIONS = {
    "Lagos": {"weight": 1.42, "delay": 0.94, "risk": 0.82},
    "Abuja": {"weight": 1.08, "delay": 0.98, "risk": 0.88},
    "Port Harcourt": {"weight": 0.86, "delay": 1.08, "risk": 1.04},
    "Ibadan": {"weight": 0.72, "delay": 1.02, "risk": 0.96},
    "Kano": {"weight": 0.66, "delay": 1.16, "risk": 1.18},
}

CHANNELS = {
    "Store": {"weight": 1.14, "repeat": 0.58, "support": 0.060},
    "Web": {"weight": 1.02, "repeat": 0.49, "support": 0.074},
    "Marketplace": {"weight": 0.82, "repeat": 0.43, "support": 0.083},
    "Partner": {"weight": 0.68, "repeat": 0.54, "support": 0.067},
}

CATEGORIES = {
    "Electronics": {"weight": 1.20, "aov": 86000, "margin": 0.235, "return": 0.071, "stockout": 0.135},
    "Home & Living": {"weight": 0.96, "aov": 52000, "margin": 0.305, "return": 0.045, "stockout": 0.087},
    "Beauty": {"weight": 0.74, "aov": 28500, "margin": 0.388, "return": 0.028, "stockout": 0.061},
    "Fashion": {"weight": 1.10, "aov": 34000, "margin": 0.332, "return": 0.096, "stockout": 0.103},
    "Grocery": {"weight": 1.34, "aov": 18500, "margin": 0.182, "return": 0.022, "stockout": 0.074},
    "Business Supplies": {"weight": 0.82, "aov": 64000, "margin": 0.274, "return": 0.035, "stockout": 0.092},
}


def quarter(month: str) -> str:
    year, month_num = month.split("-")
    return f"{year} Q{(int(month_num) - 1) // 3 + 1}"


def campaign(month_index: int, category: str) -> str:
    month_num = month_index % 12 + 1
    if month_num in {11, 12}:
        return "Peak Season"
    if month_num in {3, 6, 9}:
        return "Payday Push"
    if category in {"Fashion", "Beauty"} and month_num in {2, 5, 8}:
        return "Style Drop"
    if category == "Business Supplies" and month_num in {1, 4, 7, 10}:
        return "SME Restock"
    return "Always On"


def generate_dataset() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for month_index, month in enumerate(MONTHS):
        growth = 1 + month_index * 0.038
        season = 1 + math.sin(month_index / 1.8) * 0.045
        peak = 1.18 if month.endswith("-11") or month.endswith("-12") else 1.0
        for region, region_meta in REGIONS.items():
            for channel, channel_meta in CHANNELS.items():
                for category, category_meta in CATEGORIES.items():
                    promo = campaign(month_index, category)
                    promo_lift = {
                        "Peak Season": 1.18,
                        "Payday Push": 1.10,
                        "Style Drop": 1.08,
                        "SME Restock": 1.07,
                        "Always On": 1.0,
                    }[promo]
                    base_orders = 365
                    orders = int(
                        base_orders
                        * growth
                        * season
                        * peak
                        * promo_lift
                        * float(region_meta["weight"])
                        * float(channel_meta["weight"])
                        * float(category_meta["weight"])
                    )
                    aov = float(category_meta["aov"]) * (1 + month_index * 0.006)
                    revenue = orders * aov
                    margin = float(category_meta["margin"]) - (0.008 if channel == "Marketplace" else 0) + (0.004 if region == "Lagos" else 0)
                    gross_profit = revenue * margin
                    marketing_spend = revenue * (0.062 + (0.012 if promo != "Always On" else 0.0))
                    return_rate = float(category_meta["return"]) * (1.10 if channel == "Marketplace" else 1.0)
                    returns = int(orders * return_rate)
                    support_rate = float(channel_meta["support"]) + (0.014 if category == "Electronics" else 0.0)
                    support_tickets = int(orders * support_rate)
                    repeat_rate = min(0.72, float(channel_meta["repeat"]) + month_index * 0.006 - return_rate * 0.25)
                    active_customers = int(orders * (0.64 + repeat_rate * 0.14))
                    repeat_customers = int(active_customers * repeat_rate)
                    new_customers = max(active_customers - repeat_customers, 0)
                    churned_customers = int((new_customers * 0.055) + (returns * 0.24))
                    delay = 18 * float(region_meta["delay"]) * (1 + float(category_meta["stockout"]) * 0.55) * (1 + month_index * -0.006)
                    stockout_risk = min(0.24, float(category_meta["stockout"]) * float(region_meta["risk"]) * (1 - month_index * 0.009))
                    satisfaction = max(3.2, 4.72 - return_rate * 4.1 - stockout_risk * 2.2 - support_rate * 1.4)
                    data_quality_flags = max(1, int((35 - month_index * 1.35) * float(region_meta["risk"]) * (1.1 if channel == "Marketplace" else 0.92)))
                    rows.append(
                        {
                            "month": month,
                            "quarter": quarter(month),
                            "region": region,
                            "channel": channel,
                            "category": category,
                            "campaign": promo,
                            "orders": str(orders),
                            "revenue_ngn": f"{revenue:.0f}",
                            "cost_ngn": f"{revenue - gross_profit:.0f}",
                            "gross_profit_ngn": f"{gross_profit:.0f}",
                            "marketing_spend_ngn": f"{marketing_spend:.0f}",
                            "returns": str(returns),
                            "support_tickets": str(support_tickets),
                            "new_customers": str(new_customers),
                            "repeat_customers": str(repeat_customers),
                            "churned_customers": str(churned_customers),
                            "fulfillment_delay_hours": f"{delay:.1f}",
                            "stockout_risk_pct": f"{stockout_risk:.4f}",
                            "customer_satisfaction": f"{satisfaction:.2f}",
                            "data_quality_flags": str(data_quality_flags),
                        }
                    )
    return rows


def write_dataset(rows: list[dict[str, str]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with DATA_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def load_rows() -> list[dict[str, str]]:
    with DATA_PATH.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def n(row: dict[str, str], key: str) -> float:
    return float(row[key])


def compact_money(value: float) -> str:
    if abs(value) >= 1_000_000_000:
        return f"NGN {value / 1_000_000_000:.2f}B"
    if abs(value) >= 1_000_000:
        return f"NGN {value / 1_000_000:.1f}M"
    return f"NGN {value:,.0f}"


def compact_int(value: float) -> str:
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{value:,.0f}"


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def delta(current: float, previous: float) -> float:
    return (current - previous) / previous if previous else 0.0


def rows_for_month(rows: list[dict[str, str]], month: str) -> list[dict[str, str]]:
    return [row for row in rows if row["month"] == month]


def sum_field(rows: Iterable[dict[str, str]], key: str) -> float:
    return sum(n(row, key) for row in rows)


def weighted_average(rows: list[dict[str, str]], value_key: str, weight_key: str = "orders") -> float:
    total_weight = sum_field(rows, weight_key)
    if total_weight == 0:
        return 0.0
    return sum(n(row, value_key) * n(row, weight_key) for row in rows) / total_weight


def aggregate_by(rows: list[dict[str, str]], dimension: str) -> dict[str, dict[str, float]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row[dimension]].append(row)
    result: dict[str, dict[str, float]] = {}
    for key, items in grouped.items():
        orders = sum_field(items, "orders")
        revenue = sum_field(items, "revenue_ngn")
        profit = sum_field(items, "gross_profit_ngn")
        returns = sum_field(items, "returns")
        result[key] = {
            "orders": orders,
            "revenue": revenue,
            "profit": profit,
            "margin": profit / revenue if revenue else 0.0,
            "return_rate": returns / orders if orders else 0.0,
            "repeat_rate": sum_field(items, "repeat_customers") / (sum_field(items, "repeat_customers") + sum_field(items, "new_customers")),
            "delay": weighted_average(items, "fulfillment_delay_hours"),
            "stockout": weighted_average(items, "stockout_risk_pct"),
            "satisfaction": weighted_average(items, "customer_satisfaction"),
        }
    return result


def monthly_series(rows: list[dict[str, str]], key: str) -> list[float]:
    return [sum_field(rows_for_month(rows, month), key) for month in MONTHS]


def monthly_rate_series(rows: list[dict[str, str]], numerator: str, denominator: str) -> list[float]:
    values = []
    for month in MONTHS:
        items = rows_for_month(rows, month)
        den = sum_field(items, denominator)
        values.append(sum_field(items, numerator) / den if den else 0.0)
    return values


def line_points(values: list[float], width: int = 760, height: int = 210, pad: int = 22) -> str:
    low = min(values)
    high = max(values)
    span = high - low or 1.0
    inner_width = width - pad * 2
    inner_height = height - pad * 2
    coords = []
    for index, value in enumerate(values):
        x = pad + index * (inner_width / (len(values) - 1))
        y = pad + inner_height - ((value - low) / span * inner_height)
        coords.append(f"{x:.1f},{y:.1f}")
    return " ".join(coords)


def line_point(values: list[float], index: int, width: int = 760, height: int = 210, pad: int = 22) -> tuple[float, float]:
    low = min(values)
    high = max(values)
    span = high - low or 1.0
    inner_width = width - pad * 2
    inner_height = height - pad * 2
    x = pad + index * (inner_width / (len(values) - 1))
    y = pad + inner_height - ((values[index] - low) / span * inner_height)
    return x, y


def area_points(values: list[float], width: int = 760, height: int = 210, pad: int = 22) -> str:
    line = line_points(values, width, height, pad)
    return f"{pad},{height - pad} {line} {width - pad},{height - pad}"


def landscape_line_points(
    values: list[float],
    width: int = 720,
    height: int = 246,
    left: int = 42,
    right: int = 22,
    top: int = 24,
    bottom: int = 30,
) -> str:
    low = min(values)
    high = max(values)
    span = high - low or 1.0
    inner_width = width - left - right
    inner_height = height - top - bottom
    coords = []
    for index, value in enumerate(values):
        x = left + index * (inner_width / (len(values) - 1))
        y = top + inner_height - ((value - low) / span * inner_height)
        coords.append(f"{x:.1f},{y:.1f}")
    return " ".join(coords)


def landscape_line_point(
    values: list[float],
    index: int,
    width: int = 720,
    height: int = 246,
    left: int = 42,
    right: int = 22,
    top: int = 24,
    bottom: int = 30,
) -> tuple[float, float]:
    low = min(values)
    high = max(values)
    span = high - low or 1.0
    inner_width = width - left - right
    inner_height = height - top - bottom
    x = left + index * (inner_width / (len(values) - 1))
    y = top + inner_height - ((values[index] - low) / span * inner_height)
    return x, y


def landscape_area_points(values: list[float], width: int = 720, height: int = 246, left: int = 42, right: int = 22, bottom: int = 30) -> str:
    line = landscape_line_points(values, width=width, height=height, left=left, right=right, bottom=bottom)
    baseline = height - bottom
    return f"{left},{baseline} {line} {width - right},{baseline}"


def landscape_x_axis(width: int = 720, height: int = 246, left: int = 42, right: int = 22, bottom: int = 30) -> str:
    baseline = height - bottom
    inner_width = width - left - right
    tick_indices = [0, 3, 6, 9, 12, 15, 17]
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    marks = [f'<line class="axis" x1="{left}" y1="{baseline}" x2="{width - right}" y2="{baseline}"></line>']
    for index in tick_indices:
        year, month = MONTHS[index].split("-")
        label = month_names[int(month) - 1]
        if index == 0 or month == "01" or index == len(MONTHS) - 1:
            label = f"{label} '{year[-2:]}"
        x = left + index * (inner_width / (len(MONTHS) - 1))
        anchor = "start" if index == 0 else "end" if index == len(MONTHS) - 1 else "middle"
        marks.append(f'<line class="axis" x1="{x:.1f}" y1="{baseline}" x2="{x:.1f}" y2="{baseline + 5}"></line>')
        marks.append(f'<text class="x-axis-label" x="{x:.1f}" y="{baseline + 22}" text-anchor="{anchor}">{html.escape(label)}</text>')
    return "\n".join(marks)


def escape(value: object) -> str:
    return html.escape(str(value))


def kpi_card(label: str, value: str, change: float, note: str, icon: str) -> str:
    direction = "up" if change >= 0 else "down"
    sign = "+" if change >= 0 else ""
    return f"""
      <section class="kpi-card">
        <div class="kpi-top">
          <span class="kpi-icon">{escape(icon)}</span>
          <span class="kpi-delta {direction}">{sign}{change * 100:.1f}%</span>
        </div>
        <strong>{escape(value)}</strong>
        <p>{escape(label)}</p>
        <small>{escape(note)}</small>
      </section>
    """


def ranking_bars(items: list[tuple[str, dict[str, float]]]) -> str:
    max_revenue = max(item[1]["revenue"] for item in items) or 1.0
    rows = []
    for index, (name, metric) in enumerate(items, start=1):
        width = metric["revenue"] / max_revenue * 100
        rows.append(
            f"""
            <div class="rank-row">
              <span class="rank-number">{index}</span>
              <div class="rank-main">
                <div class="rank-label">
                  <strong>{escape(name)}</strong>
                  <span>{compact_money(metric["revenue"])}</span>
                </div>
                <div class="rank-meta">
                  <span>Margin {pct(metric["margin"])}</span>
                  <span>Returns {pct(metric["return_rate"])}</span>
                </div>
                <div class="bar-track"><div class="bar-fill" style="width:{width:.1f}%"></div></div>
              </div>
            </div>
            """
        )
    return "\n".join(rows)


def regional_grid(items: list[tuple[str, dict[str, float]]]) -> str:
    max_revenue = max(item[1]["revenue"] for item in items) or 1.0
    blocks = []
    for name, metric in items:
        intensity = metric["revenue"] / max_revenue
        status = "Watch" if metric["stockout"] > 0.09 or metric["delay"] > 20 else "Healthy"
        blocks.append(
            f"""
            <div class="region-cell" style="--heat:{intensity:.2f}">
              <div>
                <strong>{escape(name)}</strong>
                <span>{escape(status)}</span>
              </div>
              <p>{compact_money(metric["revenue"])}</p>
              <small>Margin {pct(metric["margin"])} | Delay {metric["delay"]:.1f}h</small>
            </div>
            """
        )
    return "\n".join(blocks)


def channel_mix(channels: list[tuple[str, dict[str, float]]]) -> tuple[str, str]:
    colors = ["#0b6fa4", "#2bb3a3", "#f2b544", "#ef6b5b"]
    total = sum(metric["revenue"] for _, metric in channels) or 1.0
    start = 0.0
    stops = []
    legend = []
    for index, (name, metric) in enumerate(channels):
        share = metric["revenue"] / total * 100
        end = start + share
        color = colors[index % len(colors)]
        stops.append(f"{color} {start:.1f}% {end:.1f}%")
        legend.append(
            f"""
            <div class="legend-row">
              <span class="dot" style="background:{color}"></span>
              <strong>{escape(name)}</strong>
              <span>{share:.1f}%</span>
            </div>
            """
        )
        start = end
    return ", ".join(stops), "\n".join(legend)


def customer_bars(rows: list[dict[str, str]]) -> str:
    bars = []
    months = MONTHS[-6:]
    max_total = 1.0
    totals = []
    for month in months:
        items = rows_for_month(rows, month)
        total = sum_field(items, "new_customers") + sum_field(items, "repeat_customers")
        totals.append(total)
        max_total = max(max_total, total)
    for month, total in zip(months, totals):
        items = rows_for_month(rows, month)
        new_customers = sum_field(items, "new_customers")
        repeat = sum_field(items, "repeat_customers")
        churned = sum_field(items, "churned_customers")
        new_height = new_customers / max_total * 145
        repeat_height = repeat / max_total * 145
        bars.append(
            f"""
            <div class="customer-month">
              <div class="stack" title="{escape(month)}">
                <span class="repeat" style="height:{repeat_height:.1f}px"></span>
                <span class="new" style="height:{new_height:.1f}px"></span>
              </div>
              <strong>{escape(month[-2:])}</strong>
              <small>-{compact_int(churned)}</small>
            </div>
            """
        )
    return "\n".join(bars)


def customer_quality_panel(rows: list[dict[str, str]]) -> str:
    months = MONTHS[-6:]
    month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    data = []
    max_active = 1.0
    for month in months:
        items = rows_for_month(rows, month)
        new_customers = sum_field(items, "new_customers")
        repeat_customers = sum_field(items, "repeat_customers")
        churned_customers = sum_field(items, "churned_customers")
        active_customers = new_customers + repeat_customers
        repeat_share = repeat_customers / active_customers if active_customers else 0.0
        churn_rate = churned_customers / active_customers if active_customers else 0.0
        max_active = max(max_active, active_customers)
        data.append(
            {
                "month": month,
                "label": month_labels[int(month[-2:]) - 1],
                "new": new_customers,
                "repeat": repeat_customers,
                "active": active_customers,
                "repeat_share": repeat_share,
                "churn_rate": churn_rate,
            }
        )

    first = data[0]
    latest = data[-1]
    repeat_delta = (latest["repeat_share"] - first["repeat_share"]) * 100
    churn_delta = (latest["churn_rate"] - first["churn_rate"]) * 100
    repeat_sign = "+" if repeat_delta >= 0 else ""
    churn_sign = "+" if churn_delta >= 0 else ""
    bars = []
    for item in data:
        total_height = 112 * item["active"] / max_active
        repeat_height = max(8, total_height * item["repeat_share"])
        new_height = max(8, total_height - repeat_height)
        bars.append(
            f"""
            <div class="quality-month">
              <span class="active-count">{compact_int(item["active"])}</span>
              <div class="quality-stack" title="{escape(item["month"])} active customers">
                <span class="repeat" style="height:{repeat_height:.1f}px"></span>
                <span class="new" style="height:{new_height:.1f}px"></span>
              </div>
              <strong>{escape(item["label"])}</strong>
            </div>
            """
        )

    return f"""
      <div class="quality-panel">
        <div class="quality-summary">
          <div>
            <span>Repeat share</span>
            <strong>{pct(latest["repeat_share"])}</strong>
            <small>{repeat_sign}{repeat_delta:.1f}pp vs Jan</small>
          </div>
          <div>
            <span>Churn pressure</span>
            <strong>{pct(latest["churn_rate"])}</strong>
            <small>{churn_sign}{churn_delta:.1f}pp vs Jan</small>
          </div>
        </div>
        <div class="quality-chart">{"".join(bars)}</div>
        <div class="quality-legend">
          <span><i class="legend-key" style="background:#2f8f72"></i>Repeat</span>
          <span><i class="legend-key" style="background:#2c6f9f"></i>New</span>
          <span class="quality-note">Height = active customers</span>
        </div>
      </div>
    """


def risk_scatter(categories: list[tuple[str, dict[str, float]]]) -> str:
    max_revenue = max(metric["revenue"] for _, metric in categories) or 1.0
    points = []
    left = 64
    right = 604
    top = 48
    bottom = 196
    min_return = 0.02
    max_return = 0.10
    min_margin = 0.16
    max_margin = 0.40
    for index, (name, metric) in enumerate(categories, start=1):
        return_position = min(max((metric["return_rate"] - min_return) / (max_return - min_return), 0.0), 1.0)
        margin_position = min(max((metric["margin"] - min_margin) / (max_margin - min_margin), 0.0), 1.0)
        x = left + return_position * (right - left)
        y = bottom - margin_position * (bottom - top)
        radius = 8 + metric["revenue"] / max_revenue * 15
        tone = "#ef6b5b" if metric["return_rate"] > 0.07 else "#2bb3a3" if metric["margin"] > 0.31 else "#f2b544"
        points.append(
            f"""
            <g>
              <circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" fill="{tone}" fill-opacity="0.88"></circle>
              <text class="bubble-number" x="{x:.1f}" y="{y + 4:.1f}" text-anchor="middle">{index}</text>
            </g>
            """
        )
    return "\n".join(points)


def risk_legend(categories: list[tuple[str, dict[str, float]]]) -> str:
    rows = []
    for index, (name, metric) in enumerate(categories, start=1):
        status = "Watch" if metric["return_rate"] > 0.07 else "Healthy margin" if metric["margin"] > 0.31 else "Monitor"
        rows.append(
            f"""
            <div class="risk-key-row">
              <span>{index}</span>
              <strong>{escape(name)}</strong>
              <em>{status}</em>
            </div>
            """
        )
    return "\n".join(rows)


def insight_cards(latest: list[dict[str, str]], category_items: list[tuple[str, dict[str, float]]], region_items: list[tuple[str, dict[str, float]]]) -> str:
    highest_return = max(category_items, key=lambda item: item[1]["return_rate"])
    slowest_region = max(region_items, key=lambda item: item[1]["delay"])
    repeat_rate = sum_field(latest, "repeat_customers") / (sum_field(latest, "new_customers") + sum_field(latest, "repeat_customers"))
    insights = [
        ("Merchandising", f"{highest_return[0]} return pressure is {pct(highest_return[1]['return_rate'])}. Review size, quality, and delivery promise issues before the next campaign."),
        ("Operations", f"{slowest_region[0]} fulfillment is averaging {slowest_region[1]['delay']:.1f} hours. Escalate carrier mix and warehouse handoff timing this week."),
        ("Growth", f"Repeat customers drive {pct(repeat_rate)} of current customer activity. Acquisition spend should be judged against repeat purchase quality, not traffic alone."),
    ]
    return "\n".join(
        f"""
        <article class="insight">
          <span>{escape(title)}</span>
          <p>{escape(body)}</p>
        </article>
        """
        for title, body in insights
    )


def build_summary(rows: list[dict[str, str]]) -> dict[str, object]:
    latest_month = MONTHS[-1]
    previous_month = MONTHS[-2]
    latest = rows_for_month(rows, latest_month)
    previous = rows_for_month(rows, previous_month)
    revenue = sum_field(latest, "revenue_ngn")
    previous_revenue = sum_field(previous, "revenue_ngn")
    profit = sum_field(latest, "gross_profit_ngn")
    previous_profit = sum_field(previous, "gross_profit_ngn")
    orders = sum_field(latest, "orders")
    previous_orders = sum_field(previous, "orders")
    customers = sum_field(latest, "new_customers") + sum_field(latest, "repeat_customers")
    previous_customers = sum_field(previous, "new_customers") + sum_field(previous, "repeat_customers")
    repeat_rate = sum_field(latest, "repeat_customers") / customers
    previous_repeat_rate = sum_field(previous, "repeat_customers") / previous_customers
    return {
        "period": f"{MONTHS[0]} to {latest_month}",
        "latest_month": latest_month,
        "headline_metrics": {
            "revenue": revenue,
            "revenue_delta": delta(revenue, previous_revenue),
            "gross_profit": profit,
            "gross_profit_delta": delta(profit, previous_profit),
            "orders": orders,
            "orders_delta": delta(orders, previous_orders),
            "customers": customers,
            "customers_delta": delta(customers, previous_customers),
            "repeat_rate": repeat_rate,
            "repeat_rate_delta": repeat_rate - previous_repeat_rate,
            "gross_margin": profit / revenue,
            "return_rate": sum_field(latest, "returns") / orders,
            "avg_delay_hours": weighted_average(latest, "fulfillment_delay_hours"),
        },
        "top_categories": aggregate_by(latest, "category"),
        "regions": aggregate_by(latest, "region"),
        "channels": aggregate_by(latest, "channel"),
    }


def build_html(rows: list[dict[str, str]], summary: dict[str, object]) -> str:
    metrics = summary["headline_metrics"]
    latest = rows_for_month(rows, MONTHS[-1])
    revenue_series = monthly_series(rows, "revenue_ngn")
    profit_series = monthly_series(rows, "gross_profit_ngn")
    category_items = sorted(aggregate_by(latest, "category").items(), key=lambda item: item[1]["revenue"], reverse=True)
    region_items = sorted(aggregate_by(latest, "region").items(), key=lambda item: item[1]["revenue"], reverse=True)
    channel_items = sorted(aggregate_by(latest, "channel").items(), key=lambda item: item[1]["revenue"], reverse=True)
    donut_stops, channel_legend = channel_mix(channel_items)
    header_cards = "\n".join(
        [
            kpi_card("Net revenue", compact_money(float(metrics["revenue"])), float(metrics["revenue_delta"]), "vs previous month", "REV"),
            kpi_card("Gross profit", compact_money(float(metrics["gross_profit"])), float(metrics["gross_profit_delta"]), f"margin {pct(float(metrics['gross_margin']))}", "GP"),
            kpi_card("Orders", compact_int(float(metrics["orders"])), float(metrics["orders_delta"]), "fulfilled and returned orders included", "ORD"),
            kpi_card("Customers", compact_int(float(metrics["customers"])), float(metrics["customers_delta"]), "new plus repeat customers", "CUS"),
            kpi_card("Repeat rate", pct(float(metrics["repeat_rate"])), float(metrics["repeat_rate_delta"]), f"returns {pct(float(metrics['return_rate']))}", "RPT"),
        ]
    )
    peak_index = max(range(len(revenue_series)), key=lambda index: revenue_series[index])
    peak_x, peak_y = line_point(revenue_series, peak_index)
    latest_x, latest_y = line_point(revenue_series, len(revenue_series) - 1)
    month_ticks = " ".join(
        f"<span>{escape(month[5:])}</span>"
        for month in MONTHS
    )
    template = Template(
        """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Retail Performance Control Room</title>
  <style>
    :root {
      --navy: #07355c;
      --navy-2: #0b4875;
      --ink: #17202a;
      --muted: #687686;
      --line: #dce4ed;
      --panel: #ffffff;
      --page: #f4f7fa;
      --blue: #0b6fa4;
      --teal: #2bb3a3;
      --gold: #f2b544;
      --red: #ef6b5b;
      --soft: #ecf4fb;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--ink);
      background: var(--page);
      font-family: "EB Garamond", Georgia, "Times New Roman", serif;
    }
    main {
      max-width: 1260px;
      margin: 0 auto;
      padding: 14px;
    }
    .shell {
      background: #fff;
      border: 1px solid #e8eef4;
      min-height: 100vh;
      box-shadow: 0 22px 60px rgba(13, 40, 67, .08);
    }
    .hero {
      position: relative;
      padding: 22px 28px 78px;
      color: #fff;
      background:
        linear-gradient(90deg, rgba(7, 53, 92, .98), rgba(7, 53, 92, .93)),
        radial-gradient(circle at 82% 20%, rgba(43, 179, 163, .22), transparent 35%);
    }
    .topbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid rgba(255,255,255,.28);
      padding-bottom: 18px;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
      font-weight: 800;
      font-size: 26px;
    }
    .brand-mark {
      width: 36px;
      height: 36px;
      border-radius: 7px;
      display: grid;
      place-items: center;
      background: #fff;
      color: var(--navy);
      font-size: 14px;
    }
    .report-meta {
      display: flex;
      align-items: center;
      gap: 10px;
      color: rgba(255,255,255,.76);
      font-size: 12px;
      flex-wrap: wrap;
    }
    .report-meta span {
      border: 1px solid rgba(255,255,255,.24);
      border-radius: 999px;
      padding: 7px 10px;
      background: rgba(255,255,255,.06);
    }
    .hero-grid {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 430px;
      gap: 28px;
      align-items: end;
      margin-top: 26px;
    }
    .crumb {
      color: rgba(255,255,255,.74);
      font-size: 13px;
      font-weight: 700;
      margin-bottom: 4px;
    }
    h1 {
      margin: 0;
      font-size: clamp(31px, 4vw, 50px);
      line-height: 1;
      font-weight: 800;
    }
    .subtitle {
      margin: 10px 0 0;
      max-width: 730px;
      color: rgba(255,255,255,.76);
      font-size: 16px;
      line-height: 1.5;
    }
    .filters {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
    }
    .filter label {
      display: block;
      color: rgba(255,255,255,.86);
      font-size: 13px;
      font-weight: 700;
      margin-bottom: 8px;
    }
    .select {
      display: flex;
      justify-content: space-between;
      align-items: center;
      min-height: 38px;
      border: 1px solid rgba(255,255,255,.76);
      padding: 0 12px;
      color: #fff;
      background: rgba(255,255,255,.04);
      font-size: 13px;
    }
    .select::after {
      content: "";
      width: 8px;
      height: 8px;
      border-right: 1px solid rgba(255,255,255,.9);
      border-bottom: 1px solid rgba(255,255,255,.9);
      transform: rotate(45deg);
      margin-bottom: 4px;
    }
    .dashboard {
      margin-top: -58px;
      padding: 0 32px 32px;
      position: relative;
      z-index: 2;
    }
    .kpis {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 18px;
    }
    .kpi-card, .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 12px;
      box-shadow: 0 18px 40px rgba(28, 50, 75, .08);
    }
    .kpi-card {
      min-height: 126px;
      padding: 16px;
    }
    .kpi-top {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
    }
    .kpi-icon {
      min-width: 36px;
      height: 36px;
      border-radius: 8px;
      display: grid;
      place-items: center;
      background: #eaf3fb;
      color: var(--blue);
      font-size: 11px;
      font-weight: 800;
    }
    .kpi-delta {
      color: var(--blue);
      font-size: 13px;
      font-weight: 800;
    }
    .kpi-delta.down {
      color: var(--red);
    }
    .kpi-card strong {
      display: block;
      font-size: 26px;
      line-height: 1.05;
      font-weight: 850;
    }
    .kpi-card p {
      margin: 8px 0 3px;
      color: var(--muted);
      font-size: 13px;
    }
    .kpi-card small {
      color: #a7b2be;
      font-size: 11px;
    }
    .grid {
      display: grid;
      grid-template-columns: 1.38fr .92fr;
      gap: 20px;
      margin-top: 18px;
    }
    .panel {
      padding: 20px;
      min-width: 0;
    }
    .panel-head {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: baseline;
      margin-bottom: 14px;
    }
    h2 {
      margin: 0;
      font-size: 18px;
      line-height: 1.2;
    }
    .panel-note {
      color: #9aa7b5;
      font-size: 12px;
    }
    svg {
      width: 100%;
      height: auto;
      display: block;
    }
    .axis {
      stroke: #dce4ed;
      stroke-width: 1;
    }
    .revenue-line {
      fill: none;
      stroke: var(--blue);
      stroke-width: 4;
      stroke-linecap: round;
      stroke-linejoin: round;
    }
    .profit-line {
      fill: none;
      stroke: var(--teal);
      stroke-width: 4;
      stroke-linecap: round;
      stroke-linejoin: round;
    }
    .area {
      fill: url(#revenueArea);
    }
    .ticks {
      display: grid;
      grid-template-columns: repeat(18, 1fr);
      color: #a4afba;
      font-size: 11px;
      margin: 4px 20px 0;
    }
    .chart-legend {
      display: flex;
      gap: 18px;
      margin-top: 8px;
      color: var(--muted);
      font-size: 12px;
    }
    .legend-key {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      display: inline-block;
      margin-right: 6px;
    }
    .rank-row {
      display: flex;
      align-items: center;
      gap: 12px;
      margin: 13px 0;
    }
    .rank-number {
      width: 26px;
      height: 26px;
      border-radius: 50%;
      display: grid;
      place-items: center;
      background: #edf3f8;
      color: #6a7887;
      font-size: 12px;
      font-weight: 800;
    }
    .rank-row:first-child .rank-number {
      background: var(--blue);
      color: #fff;
    }
    .rank-main {
      flex: 1;
      min-width: 0;
    }
    .rank-label {
      display: flex;
      justify-content: space-between;
      gap: 14px;
      margin-bottom: 6px;
      font-size: 13px;
    }
    .rank-label span {
      color: var(--muted);
      font-weight: 700;
    }
    .rank-meta {
      display: flex;
      gap: 10px;
      color: #8b98a7;
      font-size: 11px;
      margin-bottom: 7px;
    }
    .bar-track {
      height: 8px;
      border-radius: 999px;
      background: #edf1f5;
      overflow: hidden;
    }
    .bar-fill {
      height: 100%;
      border-radius: 999px;
      background: linear-gradient(90deg, var(--blue), var(--teal));
    }
    .thirds {
      display: grid;
      grid-template-columns: .86fr 1fr 1.14fr;
      gap: 20px;
      margin-top: 20px;
    }
    .donut-wrap {
      display: grid;
      grid-template-columns: 118px minmax(0, 1fr);
      gap: 14px;
      align-items: center;
    }
    .donut {
      width: 118px;
      height: 118px;
      border-radius: 50%;
      background: conic-gradient($donut_stops);
      position: relative;
    }
    .donut::after {
      content: "";
      position: absolute;
      inset: 26px;
      border-radius: 50%;
      background: #fff;
      box-shadow: inset 0 0 0 1px var(--line);
    }
    .legend-row {
      display: grid;
      grid-template-columns: 10px minmax(0, 1fr) 44px;
      gap: 8px;
      align-items: center;
      font-size: 12px;
      margin: 9px 0;
      min-width: 0;
    }
    .dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
    }
    .legend-row span:last-child {
      color: var(--muted);
      font-weight: 700;
      text-align: right;
    }
    .legend-row strong {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .customer-bars {
      display: flex;
      justify-content: space-between;
      align-items: end;
      min-height: 190px;
      gap: 10px;
      padding-top: 12px;
    }
    .customer-month {
      flex: 1;
      text-align: center;
      color: var(--muted);
      font-size: 11px;
    }
    .stack {
      height: 150px;
      display: flex;
      flex-direction: column-reverse;
      justify-content: flex-start;
      gap: 2px;
      align-items: stretch;
      margin-bottom: 8px;
    }
    .stack span {
      display: block;
      border-radius: 6px 6px 0 0;
    }
    .stack .new {
      background: var(--blue);
    }
    .stack .repeat {
      background: var(--teal);
    }
    .customer-month small {
      display: block;
      color: var(--red);
      margin-top: 2px;
    }
    .region-grid {
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      gap: 10px;
    }
    .region-cell {
      min-height: 118px;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: linear-gradient(180deg, rgba(11, 111, 164, calc(.08 + var(--heat) * .17)), #fff);
    }
    .region-cell div {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      align-items: center;
      color: var(--muted);
      font-size: 11px;
    }
    .region-cell div strong {
      color: var(--ink);
      font-size: 13px;
    }
    .region-cell p {
      margin: 18px 0 8px;
      font-weight: 850;
      font-size: 19px;
    }
    .region-cell small {
      color: var(--muted);
      font-size: 11px;
      line-height: 1.4;
    }
    .scatter text {
      fill: #52606f;
      font-size: 12px;
      font-weight: 700;
    }
    .scatter .bubble-number {
      fill: #fff;
      font-size: 11px;
      font-weight: 850;
    }
    .scatter-label {
      fill: #9aa7b5;
      font-size: 11px;
      font-weight: 700;
    }
    .risk-legend {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 7px 12px;
      margin-top: 8px;
    }
    .risk-key-row {
      display: grid;
      grid-template-columns: 22px minmax(0, 1fr);
      gap: 8px;
      align-items: center;
      font-size: 11px;
      color: var(--muted);
    }
    .risk-key-row span {
      width: 20px;
      height: 20px;
      display: grid;
      place-items: center;
      border-radius: 50%;
      background: #edf3f8;
      color: var(--blue);
      font-weight: 850;
    }
    .risk-key-row strong {
      min-width: 0;
      color: var(--ink);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .risk-key-row em {
      grid-column: 2;
      margin-top: -4px;
      color: #8b98a7;
      font-style: normal;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .insights {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 16px;
      margin-top: 20px;
    }
    .insight {
      border-left: 4px solid var(--blue);
      padding: 14px 16px;
      background: #f8fbfd;
      border-radius: 8px;
    }
    .insight span {
      display: block;
      color: var(--blue);
      font-size: 12px;
      font-weight: 850;
      text-transform: uppercase;
      margin-bottom: 8px;
    }
    .insight p {
      margin: 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.55;
    }
    @media (max-width: 900px) {
      .kpis {
        grid-template-columns: repeat(2, 1fr);
      }
      .grid, .thirds, .hero-grid, .insights {
        grid-template-columns: 1fr;
      }
      .dashboard {
        padding: 0 18px 24px;
      }
    }
    @media (max-width: 720px) {
      main {
        padding: 0;
      }
      .hero {
        padding: 20px 18px 92px;
      }
      .topbar {
        align-items: flex-start;
      }
      .report-meta {
        display: none;
      }
      .filters, .kpis, .region-grid {
        grid-template-columns: 1fr;
      }
      .donut-wrap {
        grid-template-columns: 1fr;
        justify-items: center;
      }
      .kpi-card strong {
        font-size: 24px;
      }
      .ticks {
        display: none;
      }
    }
  </style>
</head>
<body>
  <main>
    <div class="shell">
      <section class="hero">
        <div class="topbar">
          <div class="brand"><span class="brand-mark">KR</span> Kora Retail Group</div>
          <div class="report-meta"><span>Closed month: Jun 2026</span><span>Rows: $row_count</span><span>Source: orders + support + fulfilment</span></div>
        </div>
        <div class="hero-grid">
          <div>
            <div class="crumb">Executive Review / Retail Performance</div>
            <h1>Retail Performance Control Room</h1>
            <p class="subtitle">A closed-month operating view for revenue quality, profit leakage, customer retention, returns, fulfilment speed, and market-level risk.</p>
          </div>
          <div class="filters">
            <div class="filter"><label>Market</label><div class="select"><span>All regions</span></div></div>
            <div class="filter"><label>Channel</label><div class="select"><span>Omnichannel</span></div></div>
            <div class="filter"><label>Period</label><div class="select"><span>Jan 2025-Jun 2026</span></div></div>
            <div class="filter"><label>View</label><div class="select"><span>Executive</span></div></div>
          </div>
        </div>
      </section>

      <section class="dashboard">
        <div class="kpis">$header_cards</div>

        <section class="grid">
          <article class="panel">
            <div class="panel-head"><h2>Revenue and Gross Profit Trend</h2><span class="panel-note">18-month closed-period view</span></div>
            <svg viewBox="0 0 760 250" role="img" aria-label="Revenue and gross profit trend chart">
              <defs>
                <linearGradient id="revenueArea" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0%" stop-color="#0b6fa4" stop-opacity=".22"></stop>
                  <stop offset="100%" stop-color="#0b6fa4" stop-opacity="0"></stop>
                </linearGradient>
              </defs>
              <line class="axis" x1="22" y1="228" x2="738" y2="228"></line>
              <line class="axis" x1="22" y1="170" x2="738" y2="170"></line>
              <line class="axis" x1="22" y1="112" x2="738" y2="112"></line>
              <polygon class="area" points="$revenue_area"></polygon>
              <polyline class="revenue-line" points="$revenue_points"></polyline>
              <polyline class="profit-line" points="$profit_points"></polyline>
              <circle cx="$peak_x" cy="$peak_y" r="5" fill="#fff" stroke="#f2b544" stroke-width="3"></circle>
              <text x="$peak_label_x" y="$peak_label_y" fill="#9a6a00" font-size="12" font-weight="800">Peak: $peak_month</text>
              <circle cx="$latest_revenue_x" cy="$latest_revenue_y" r="7" fill="#fff" stroke="#0b6fa4" stroke-width="4"></circle>
              <text x="$latest_revenue_label_x" y="$latest_revenue_label_y" fill="#0b6fa4" font-size="12" font-weight="800">Jun close</text>
            </svg>
            <div class="ticks">$month_ticks</div>
            <div class="chart-legend">
              <span><i class="legend-key" style="background:#0b6fa4"></i>Revenue</span>
              <span><i class="legend-key" style="background:#2bb3a3"></i>Gross profit</span>
            </div>
          </article>

          <article class="panel">
            <div class="panel-head"><h2>Category Revenue Ranking</h2><span class="panel-note">top 6 | latest month</span></div>
            $ranking_bars
          </article>
        </section>

        <section class="thirds">
          <article class="panel">
            <div class="panel-head"><h2>Channel Mix</h2><span class="panel-note">share of revenue</span></div>
            <div class="donut-wrap">
              <div class="donut"></div>
              <div>$channel_legend</div>
            </div>
          </article>

          <article class="panel">
            <div class="panel-head"><h2>Acquisition vs Retention</h2><span class="panel-note">last 6 months | churn noted</span></div>
            <div class="customer-bars">$customer_bars</div>
            <div class="chart-legend">
              <span><i class="legend-key" style="background:#0b6fa4"></i>New</span>
              <span><i class="legend-key" style="background:#2bb3a3"></i>Repeat</span>
            </div>
          </article>

          <article class="panel">
            <div class="panel-head"><h2>Margin Risk & Returns</h2><span class="panel-note">bubble size = revenue</span></div>
            <svg class="scatter" viewBox="0 0 650 292" role="img" aria-label="Margin and returns risk chart">
              <line class="axis" x1="50" y1="260" x2="620" y2="260"></line>
              <line class="axis" x1="50" y1="62" x2="50" y2="260"></line>
              <line class="axis" x1="335" y1="62" x2="335" y2="260" stroke-dasharray="5 6"></line>
              <line class="axis" x1="50" y1="158" x2="620" y2="158" stroke-dasharray="5 6"></line>
              $risk_scatter
              <text class="scatter-label" x="50" y="284">Lower return rate</text>
              <text class="scatter-label" x="500" y="284">Higher return rate</text>
              <text class="scatter-label" x="54" y="52">Higher margin</text>
            </svg>
            <div class="risk-legend">$risk_legend</div>
          </article>
        </section>

        <section class="panel" style="margin-top:20px">
          <div class="panel-head"><h2>Regional Performance Grid</h2><span class="panel-note">revenue intensity, delay, and margin</span></div>
          <div class="region-grid">$regional_grid</div>
        </section>

        <section class="insights">$insight_cards</section>
      </section>
    </div>
  </main>
</body>
</html>
"""
    )
    return template.substitute(
        row_count=f"{len(rows):,}",
        header_cards=header_cards,
        revenue_area=area_points(revenue_series),
        revenue_points=line_points(revenue_series),
        profit_points=line_points(profit_series),
        peak_x=f"{peak_x:.1f}",
        peak_y=f"{peak_y:.1f}",
        peak_label_x=f"{min(peak_x + 12, 620):.1f}",
        peak_label_y=f"{max(peak_y - 12, 18):.1f}",
        peak_month=MONTHS[peak_index],
        latest_revenue_x=f"{latest_x:.1f}",
        latest_revenue_y=f"{latest_y:.1f}",
        latest_revenue_label_x=f"{max(latest_x - 72, 24):.1f}",
        latest_revenue_label_y=f"{max(latest_y - 18, 18):.1f}",
        month_ticks=month_ticks,
        ranking_bars=ranking_bars(category_items),
        donut_stops=donut_stops,
        channel_legend=channel_legend,
        customer_bars=customer_bars(rows),
        risk_scatter=risk_scatter(category_items),
        risk_legend=risk_legend(category_items),
        regional_grid=regional_grid(region_items),
        insight_cards=insight_cards(latest, category_items, region_items),
    )


def compact_kpi(label: str, value: str, delta_value: float, note: str) -> str:
    direction = "positive" if delta_value >= 0 else "negative"
    sign = "+" if delta_value >= 0 else ""
    return f"""
      <article class="metric-tile">
        <div>
          <span>{escape(label)}</span>
          <strong>{escape(value)}</strong>
        </div>
        <p class="{direction}">{sign}{delta_value * 100:.1f}%</p>
        <small>{escape(note)}</small>
      </article>
    """


def channel_share_bars(channels: list[tuple[str, dict[str, float]]]) -> str:
    max_revenue = max(metric["revenue"] for _, metric in channels) or 1.0
    rows = []
    for name, metric in channels:
        width = metric["revenue"] / max_revenue * 100
        rows.append(
            f"""
            <div class="channel-row">
              <div class="channel-label">
                <strong>{escape(name)}</strong>
                <span>{compact_money(metric["revenue"])}</span>
              </div>
              <div class="channel-track">
                <div style="width:{width:.1f}%"></div>
              </div>
              <small>Margin {pct(metric["margin"])} | Repeat {pct(metric["repeat_rate"])}</small>
            </div>
            """
        )
    return "\n".join(rows)


def performance_table(categories: list[tuple[str, dict[str, float]]]) -> str:
    rows = []
    for name, metric in categories:
        risk = "High" if metric["return_rate"] > 0.07 else "Low" if metric["margin"] > 0.31 else "Medium"
        rows.append(
            f"""
            <tr>
              <td>{escape(name)}</td>
              <td>{compact_money(metric["revenue"])}</td>
              <td>{pct(metric["margin"])}</td>
              <td>{pct(metric["return_rate"])}</td>
              <td><span class="risk-pill {risk.lower()}">{risk}</span></td>
            </tr>
            """
        )
    return "\n".join(rows)


def build_html(rows: list[dict[str, str]], summary: dict[str, object]) -> str:
    metrics = summary["headline_metrics"]
    latest = rows_for_month(rows, MONTHS[-1])
    revenue_series = monthly_series(rows, "revenue_ngn")
    profit_series = monthly_series(rows, "gross_profit_ngn")
    category_items = sorted(aggregate_by(latest, "category").items(), key=lambda item: item[1]["revenue"], reverse=True)
    region_items = sorted(aggregate_by(latest, "region").items(), key=lambda item: item[1]["revenue"], reverse=True)
    channel_items = sorted(aggregate_by(latest, "channel").items(), key=lambda item: item[1]["revenue"], reverse=True)
    peak_index = max(range(len(revenue_series)), key=lambda index: revenue_series[index])
    peak_x, peak_y = line_point(revenue_series, peak_index)
    latest_x, latest_y = line_point(revenue_series, len(revenue_series) - 1)
    metric_tiles = "\n".join(
        [
            compact_kpi("Revenue", compact_money(float(metrics["revenue"])), float(metrics["revenue_delta"]), "closed month"),
            compact_kpi("Gross profit", compact_money(float(metrics["gross_profit"])), float(metrics["gross_profit_delta"]), f"margin {pct(float(metrics['gross_margin']))}"),
            compact_kpi("Orders", compact_int(float(metrics["orders"])), float(metrics["orders_delta"]), "all fulfilled orders"),
            compact_kpi("Customers", compact_int(float(metrics["customers"])), float(metrics["customers_delta"]), "active customers"),
            compact_kpi("Repeat rate", pct(float(metrics["repeat_rate"])), float(metrics["repeat_rate_delta"]), f"return rate {pct(float(metrics['return_rate']))}"),
        ]
    )
    month_ticks = " ".join(f"<span>{escape(month[5:])}</span>" for month in MONTHS)
    template = Template(
        """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Retail Revenue Leakage Review</title>
  <style>
    :root {
      --charcoal: #172126;
      --charcoal-2: #202c32;
      --paper: #f1f4f2;
      --panel: #ffffff;
      --ink: #182027;
      --muted: #697780;
      --line: #d8e0dc;
      --green: #2f8f72;
      --blue: #2c6f9f;
      --amber: #c68a2f;
      --red: #c9574b;
      --mint: #dceee8;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--ink);
      background: var(--paper);
      font-family: "EB Garamond", Georgia, "Times New Roman", serif;
    }
    main {
      max-width: 1420px;
      margin: 0 auto;
      padding: 18px;
    }
    .workbook {
      display: grid;
      grid-template-columns: 245px minmax(0, 1fr);
      min-height: calc(100vh - 36px);
      border: 1px solid #ccd7d1;
      background: var(--panel);
      box-shadow: 0 22px 60px rgba(34, 47, 54, .12);
    }
    .rail {
      background: var(--charcoal);
      color: #eaf2ef;
      padding: 22px 18px;
      display: flex;
      flex-direction: column;
      gap: 20px;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
      font-weight: 850;
      font-size: 18px;
    }
    .mark {
      width: 34px;
      height: 34px;
      border-radius: 6px;
      background: #f7fbf9;
      color: var(--charcoal);
      display: grid;
      place-items: center;
      font-size: 13px;
      font-weight: 900;
    }
    .rail-section {
      border-top: 1px solid rgba(255,255,255,.12);
      padding-top: 18px;
    }
    .rail-label {
      display: block;
      color: rgba(234,242,239,.56);
      font-size: 11px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: .08em;
      margin-bottom: 10px;
    }
    .filter-chip {
      display: flex;
      justify-content: space-between;
      align-items: center;
      border: 1px solid rgba(255,255,255,.18);
      border-radius: 6px;
      padding: 10px 11px;
      margin-bottom: 8px;
      background: rgba(255,255,255,.04);
      font-size: 13px;
    }
    .filter-chip::after {
      content: "";
      width: 7px;
      height: 7px;
      border-right: 1px solid rgba(255,255,255,.76);
      border-bottom: 1px solid rgba(255,255,255,.76);
      transform: rotate(45deg);
      margin-bottom: 4px;
    }
    .rail-metric strong {
      display: block;
      font-size: 22px;
      line-height: 1;
      margin-bottom: 4px;
    }
    .rail-metric span {
      color: rgba(234,242,239,.62);
      font-size: 12px;
      line-height: 1.45;
    }
    .report {
      min-width: 0;
      padding: 26px;
      background:
        linear-gradient(180deg, rgba(220,238,232,.75), rgba(241,244,242,0) 260px),
        var(--paper);
    }
    .report-top {
      display: flex;
      justify-content: space-between;
      gap: 24px;
      align-items: flex-start;
      margin-bottom: 18px;
    }
    .eyebrow {
      color: var(--green);
      font-size: 12px;
      font-weight: 900;
      text-transform: uppercase;
      letter-spacing: .08em;
      margin-bottom: 8px;
    }
    h1 {
      margin: 0;
      font-size: clamp(30px, 4vw, 46px);
      line-height: 1.03;
      letter-spacing: 0;
    }
    .summary {
      max-width: 690px;
      margin: 10px 0 0;
      color: var(--muted);
      line-height: 1.55;
      font-size: 15px;
    }
    .source-card {
      min-width: 250px;
      background: rgba(255,255,255,.76);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.55;
    }
    .source-card strong {
      display: block;
      color: var(--ink);
      font-size: 14px;
      margin-bottom: 3px;
    }
    .metric-strip {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 12px;
      margin: 18px 0;
    }
    .metric-tile {
      position: relative;
      min-height: 116px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 15px;
      box-shadow: 0 10px 25px rgba(32, 44, 50, .06);
    }
    .metric-tile::before {
      content: "";
      position: absolute;
      inset: 0 auto 0 0;
      width: 4px;
      border-radius: 8px 0 0 8px;
      background: var(--green);
    }
    .metric-tile span {
      display: block;
      color: var(--muted);
      font-size: 12px;
      font-weight: 750;
      margin-bottom: 8px;
      padding-right: 58px;
    }
    .metric-tile strong {
      display: block;
      font-size: 25px;
      line-height: 1.02;
    }
    .metric-tile p {
      position: absolute;
      top: 15px;
      right: 15px;
      margin: 0;
      font-size: 12px;
      font-weight: 900;
    }
    .metric-tile small {
      position: absolute;
      left: 15px;
      right: 15px;
      bottom: 13px;
      color: #8c9aa2;
      font-size: 11px;
    }
    .positive { color: var(--green); }
    .negative { color: var(--red); }
    .canvas-grid {
      display: grid;
      grid-template-columns: 1.3fr .8fr;
      gap: 14px;
      align-items: start;
    }
    .lower-grid {
      display: grid;
      grid-template-columns: .85fr 1fr 1.15fr;
      gap: 14px;
      margin-top: 14px;
      align-items: start;
    }
    .panel {
      min-width: 0;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      box-shadow: 0 10px 25px rgba(32, 44, 50, .055);
    }
    .panel-head {
      display: flex;
      justify-content: space-between;
      align-items: start;
      gap: 12px;
      margin-bottom: 14px;
    }
    h2 {
      margin: 0;
      font-size: 17px;
      line-height: 1.2;
    }
    .panel-note {
      color: #8d9aa4;
      font-size: 12px;
      text-align: right;
    }
    svg {
      display: block;
      width: 100%;
      height: auto;
    }
    .axis { stroke: #dbe3df; stroke-width: 1; }
    .area { fill: url(#revenueArea); }
    .revenue-line, .profit-line {
      fill: none;
      stroke-width: 3.4;
      stroke-linecap: round;
      stroke-linejoin: round;
    }
    .revenue-line { stroke: var(--green); }
    .profit-line { stroke: var(--blue); }
    .ticks {
      display: grid;
      grid-template-columns: repeat(18, 1fr);
      color: #95a29a;
      font-size: 10px;
      margin: 6px 20px 0;
    }
    .chart-legend {
      display: flex;
      gap: 14px;
      margin-top: 9px;
      color: var(--muted);
      font-size: 12px;
    }
    .legend-key {
      display: inline-block;
      width: 9px;
      height: 9px;
      border-radius: 50%;
      margin-right: 6px;
    }
    .rank-row {
      display: flex;
      gap: 10px;
      align-items: center;
      margin: 12px 0;
    }
    .rank-number {
      width: 24px;
      height: 24px;
      display: grid;
      place-items: center;
      border-radius: 6px;
      background: #edf3ef;
      color: var(--green);
      font-size: 12px;
      font-weight: 900;
    }
    .rank-main { flex: 1; min-width: 0; }
    .rank-label {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      margin-bottom: 5px;
      font-size: 13px;
    }
    .rank-label span {
      color: var(--muted);
      font-weight: 750;
    }
    .rank-meta {
      display: flex;
      gap: 10px;
      color: #8d9aa4;
      font-size: 11px;
      margin-bottom: 6px;
    }
    .bar-track, .channel-track {
      height: 8px;
      border-radius: 999px;
      overflow: hidden;
      background: #edf2ef;
    }
    .bar-fill, .channel-track div {
      height: 100%;
      border-radius: 999px;
      background: linear-gradient(90deg, var(--green), var(--blue));
    }
    .channel-row {
      margin: 14px 0;
    }
    .channel-label {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 7px;
      font-size: 13px;
    }
    .channel-label span {
      color: var(--muted);
      font-weight: 800;
    }
    .channel-row small {
      display: block;
      color: #8d9aa4;
      margin-top: 6px;
      font-size: 11px;
    }
    .customer-bars {
      display: flex;
      justify-content: space-between;
      align-items: end;
      gap: 8px;
      min-height: 180px;
    }
    .customer-month {
      flex: 1;
      text-align: center;
      color: var(--muted);
      font-size: 11px;
    }
    .stack {
      height: 142px;
      display: flex;
      flex-direction: column-reverse;
      justify-content: flex-start;
      gap: 2px;
      margin-bottom: 7px;
    }
    .stack span {
      display: block;
      border-radius: 4px 4px 0 0;
    }
    .stack .new { background: var(--blue); }
    .stack .repeat { background: var(--green); }
    .customer-month small {
      color: var(--red);
      display: block;
      margin-top: 2px;
    }
    .scatter .bubble-number {
      fill: #fff;
      font-size: 11px;
      font-weight: 900;
    }
    .scatter .axis-tick {
      fill: #8d9aa4;
      font-size: 10px;
      font-weight: 850;
    }
    .scatter-label {
      fill: #8d9aa4;
      font-size: 11px;
      font-weight: 750;
    }
    .risk-legend {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 7px 12px;
      margin-top: 8px;
    }
    .risk-key-row {
      display: grid;
      grid-template-columns: 22px minmax(0, 1fr);
      gap: 8px;
      align-items: center;
      font-size: 11px;
      color: var(--muted);
    }
    .risk-key-row span {
      width: 20px;
      height: 20px;
      display: grid;
      place-items: center;
      border-radius: 5px;
      background: #edf3ef;
      color: var(--green);
      font-weight: 900;
    }
    .risk-key-row strong {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .risk-key-row em {
      grid-column: 2;
      margin-top: -4px;
      color: #8d9aa4;
      font-style: normal;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .region-grid {
      display: grid;
      grid-template-columns: repeat(5, 1fr);
      gap: 9px;
    }
    .region-cell {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      min-height: 102px;
      background: linear-gradient(180deg, rgba(47,143,114, calc(.05 + var(--heat) * .16)), #fff);
    }
    .region-cell div {
      display: flex;
      justify-content: space-between;
      gap: 8px;
      font-size: 11px;
      color: var(--muted);
    }
    .region-cell strong {
      color: var(--ink);
      font-size: 13px;
    }
    .region-cell p {
      margin: 16px 0 7px;
      font-weight: 900;
      font-size: 18px;
    }
    .region-cell small {
      color: var(--muted);
      font-size: 11px;
      line-height: 1.45;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }
    th, td {
      padding: 9px 8px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      white-space: nowrap;
    }
    th {
      color: var(--muted);
      font-size: 10px;
      text-transform: uppercase;
      letter-spacing: .06em;
    }
    .risk-pill {
      display: inline-block;
      min-width: 58px;
      text-align: center;
      padding: 4px 7px;
      border-radius: 999px;
      font-size: 10px;
      font-weight: 850;
    }
    .risk-pill.high { color: #8f2f28; background: #fae7e4; }
    .risk-pill.medium { color: #8a5b15; background: #f7ecd8; }
    .risk-pill.low { color: #236b55; background: #def1e9; }
    .insights {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 14px;
      margin-top: 14px;
    }
    .insight {
      background: var(--charcoal-2);
      color: #edf6f2;
      border-radius: 8px;
      padding: 15px;
    }
    .insight span {
      display: block;
      color: #9dd8c5;
      font-size: 11px;
      font-weight: 900;
      text-transform: uppercase;
      letter-spacing: .07em;
      margin-bottom: 8px;
    }
    .insight p {
      margin: 0;
      color: rgba(237,246,242,.78);
      font-size: 13px;
      line-height: 1.55;
    }
    @media (max-width: 760px) {
      .workbook { grid-template-columns: 1fr; }
      .rail { display: block; }
      .rail-section { margin-top: 16px; }
      .metric-strip { grid-template-columns: repeat(2, 1fr); }
      .canvas-grid, .lower-grid, .insights { grid-template-columns: 1fr; }
    }
    @media (max-width: 720px) {
      main { padding: 0; }
      .report { padding: 18px; }
      .report-top { flex-direction: column; }
      .metric-strip, .region-grid { grid-template-columns: 1fr; }
      .source-card { min-width: 0; width: 100%; }
      .ticks { display: none; }
      .metric-tile strong { font-size: 22px; }
    }
  </style>
</head>
<body>
  <main>
    <section class="workbook">
      <aside class="rail">
        <div class="brand"><span class="mark">KR</span><span>Kora Retail Group</span></div>
        <div class="rail-section">
          <span class="rail-label">Report Filters</span>
          <div class="filter-chip"><span>All regions</span></div>
          <div class="filter-chip"><span>Omnichannel</span></div>
          <div class="filter-chip"><span>Jan 2025-Jun 2026</span></div>
          <div class="filter-chip"><span>Executive view</span></div>
        </div>
        <div class="rail-section rail-metric">
          <span class="rail-label">Data Model</span>
          <strong>$row_count rows</strong>
          <span>Orders, customers, support, returns, fulfilment, category, channel, campaign, and region-level data.</span>
        </div>
        <div class="rail-section rail-metric">
          <span class="rail-label">Current Question</span>
          <strong>Where is growth leaking?</strong>
          <span>Management view focused on revenue quality, customer retention, return pressure, and operational risk.</span>
        </div>
      </aside>

      <section class="report">
        <header class="report-top">
          <div>
            <div class="eyebrow">Closed Month Review | June 2026</div>
            <h1>Revenue Leakage Review</h1>
            <p class="summary">A retail performance dashboard built to separate healthy growth from hidden leakage across margin, returns, retention, fulfilment, and regional execution.</p>
          </div>
          <aside class="source-card">
            <strong>Analyst note</strong>
            Revenue is still expanding, but the review should focus on whether gross profit, repeat customers, and returns are moving in the same direction.
          </aside>
        </header>

        <section class="metric-strip">$metric_tiles</section>

        <section class="canvas-grid">
          <article class="panel">
            <div class="panel-head"><h2>Revenue and Profit Movement</h2><span class="panel-note">18 months | closed periods</span></div>
            <svg viewBox="0 0 760 250" role="img" aria-label="Revenue and gross profit trend chart">
              <defs>
                <linearGradient id="revenueArea" x1="0" x2="0" y1="0" y2="1">
                  <stop offset="0%" stop-color="#2f8f72" stop-opacity=".20"></stop>
                  <stop offset="100%" stop-color="#2f8f72" stop-opacity="0"></stop>
                </linearGradient>
              </defs>
              <line class="axis" x1="22" y1="228" x2="738" y2="228"></line>
              <line class="axis" x1="22" y1="170" x2="738" y2="170"></line>
              <line class="axis" x1="22" y1="112" x2="738" y2="112"></line>
              <polygon class="area" points="$revenue_area"></polygon>
              <polyline class="revenue-line" points="$revenue_points"></polyline>
              <polyline class="profit-line" points="$profit_points"></polyline>
              <circle cx="$peak_x" cy="$peak_y" r="5" fill="#fff" stroke="#c68a2f" stroke-width="3"></circle>
              <text x="$peak_label_x" y="$peak_label_y" fill="#8a5b15" font-size="12" font-weight="800">Peak: $peak_month</text>
              <circle cx="$latest_revenue_x" cy="$latest_revenue_y" r="6" fill="#fff" stroke="#2f8f72" stroke-width="3"></circle>
              <text x="$latest_revenue_label_x" y="$latest_revenue_label_y" fill="#236b55" font-size="12" font-weight="800">Jun close</text>
            </svg>
            <div class="ticks">$month_ticks</div>
            <div class="chart-legend">
              <span><i class="legend-key" style="background:#2f8f72"></i>Revenue</span>
              <span><i class="legend-key" style="background:#2c6f9f"></i>Gross profit</span>
            </div>
          </article>

          <article class="panel">
            <div class="panel-head"><h2>Category Contribution</h2><span class="panel-note">revenue, margin, returns</span></div>
            $ranking_bars
          </article>
        </section>

        <section class="lower-grid">
          <article class="panel">
            <div class="panel-head"><h2>Channel Economics</h2><span class="panel-note">latest month</span></div>
            $channel_bars
          </article>

          <article class="panel">
            <div class="panel-head"><h2>Customer Mix</h2><span class="panel-note">new, repeat, churned</span></div>
            <div class="customer-bars">$customer_bars</div>
            <div class="chart-legend">
              <span><i class="legend-key" style="background:#2c6f9f"></i>New</span>
              <span><i class="legend-key" style="background:#2f8f72"></i>Repeat</span>
            </div>
          </article>

          <article class="panel">
            <div class="panel-head"><h2>Return Pressure vs Margin</h2><span class="panel-note">bubble size = revenue</span></div>
            <svg class="scatter" viewBox="0 0 650 240" role="img" aria-label="Margin and returns risk chart">
              <line class="axis" x1="64" y1="196" x2="604" y2="196"></line>
              <line class="axis" x1="64" y1="48" x2="64" y2="196"></line>
              <line class="axis" x1="334" y1="48" x2="334" y2="196" stroke-dasharray="5 6"></line>
              <line class="axis" x1="64" y1="122" x2="604" y2="122" stroke-dasharray="5 6"></line>
              <text class="axis-tick" x="56" y="200" text-anchor="end">16%</text>
              <text class="axis-tick" x="56" y="126" text-anchor="end">28%</text>
              <text class="axis-tick" x="56" y="52" text-anchor="end">40%</text>
              <text class="axis-tick" x="64" y="218" text-anchor="middle">2%</text>
              <text class="axis-tick" x="334" y="218" text-anchor="middle">6%</text>
              <text class="axis-tick" x="604" y="218" text-anchor="middle">10%</text>
              $risk_scatter
              <text class="scatter-label" x="64" y="236">Lower returns</text>
              <text class="scatter-label" x="516" y="236">Higher returns</text>
              <text class="scatter-label" x="68" y="36">Margin rate</text>
            </svg>
            <div class="risk-legend">$risk_legend</div>
          </article>
        </section>

        <section class="panel" style="margin-top:14px">
          <div class="panel-head"><h2>Regional Execution Heatmap</h2><span class="panel-note">revenue intensity, margin, fulfilment delay</span></div>
          <div class="region-grid">$regional_grid</div>
        </section>

        <section class="panel" style="margin-top:14px">
          <div class="panel-head"><h2>Category Risk Register</h2><span class="panel-note">management review table</span></div>
          <table>
            <thead>
              <tr><th>Category</th><th>Revenue</th><th>Margin</th><th>Returns</th><th>Risk</th></tr>
            </thead>
            <tbody>$performance_table</tbody>
          </table>
        </section>

        <section class="insights">$insight_cards</section>
      </section>
    </section>
  </main>
</body>
</html>
"""
    )
    return template.substitute(
        row_count=f"{len(rows):,}",
        metric_tiles=metric_tiles,
        revenue_area=area_points(revenue_series),
        revenue_points=line_points(revenue_series),
        profit_points=line_points(profit_series),
        peak_x=f"{peak_x:.1f}",
        peak_y=f"{peak_y:.1f}",
        peak_label_x=f"{min(peak_x + 12, 620):.1f}",
        peak_label_y=f"{max(peak_y - 12, 18):.1f}",
        peak_month=MONTHS[peak_index],
        latest_revenue_x=f"{latest_x:.1f}",
        latest_revenue_y=f"{latest_y:.1f}",
        latest_revenue_label_x=f"{max(latest_x - 72, 24):.1f}",
        latest_revenue_label_y=f"{max(latest_y - 18, 18):.1f}",
        month_ticks=month_ticks,
        ranking_bars=ranking_bars(category_items),
        channel_bars=channel_share_bars(channel_items),
        customer_bars=customer_bars(rows),
        risk_scatter=risk_scatter(category_items),
        risk_legend=risk_legend(category_items),
        regional_grid=regional_grid(region_items),
        performance_table=performance_table(category_items),
        insight_cards=insight_cards(latest, category_items, region_items),
    )


def build_landscape_html(rows: list[dict[str, str]], summary: dict[str, object]) -> str:
    metrics = summary["headline_metrics"]
    latest = rows_for_month(rows, MONTHS[-1])
    revenue_series = monthly_series(rows, "revenue_ngn")
    profit_series = monthly_series(rows, "gross_profit_ngn")
    category_items = sorted(aggregate_by(latest, "category").items(), key=lambda item: item[1]["revenue"], reverse=True)
    channel_items = sorted(aggregate_by(latest, "channel").items(), key=lambda item: item[1]["revenue"], reverse=True)
    region_items = sorted(aggregate_by(latest, "region").items(), key=lambda item: item[1]["revenue"], reverse=True)
    peak_index = max(range(len(revenue_series)), key=lambda index: revenue_series[index])
    peak_x, peak_y = landscape_line_point(revenue_series, peak_index)
    latest_x, latest_y = landscape_line_point(revenue_series, len(revenue_series) - 1)
    revenue_delta = float(metrics["revenue_delta"])
    profit_delta = float(metrics["gross_profit_delta"])
    return_rate = float(metrics["return_rate"])
    repeat_rate = float(metrics["repeat_rate"])
    profit_signal = "Profit quality holding" if profit_delta >= revenue_delta * 0.9 else "Profit quality lagging"
    return_signal = "Returns contained" if return_rate < 0.06 else "Returns need review"
    signal_pills = "\n".join(
        [
            f'<span><strong>{escape(profit_signal)}</strong> GP {profit_delta * 100:+.1f}% vs revenue {revenue_delta * 100:+.1f}%</span>',
            f'<span><strong>{escape(return_signal)}</strong> return rate {pct(return_rate)}</span>',
            f'<span><strong>Retention base</strong> repeat share {pct(repeat_rate)}</span>',
        ]
    )
    metric_tiles = "\n".join(
        [
            compact_kpi("Revenue", compact_money(float(metrics["revenue"])), float(metrics["revenue_delta"]), "closed month"),
            compact_kpi("Gross profit", compact_money(float(metrics["gross_profit"])), float(metrics["gross_profit_delta"]), f"margin {pct(float(metrics['gross_margin']))}"),
            compact_kpi("Orders", compact_int(float(metrics["orders"])), float(metrics["orders_delta"]), "fulfilled orders"),
            compact_kpi("Customers", compact_int(float(metrics["customers"])), float(metrics["customers_delta"]), "active customers"),
            compact_kpi("Repeat rate", pct(float(metrics["repeat_rate"])), float(metrics["repeat_rate_delta"]), f"returns {pct(float(metrics['return_rate']))}"),
        ]
    )
    template = Template(
        """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LinkedIn Landscape - Retail Revenue Leakage Review</title>
  <style>
    :root {
      --charcoal: #172126;
      --charcoal-2: #202c32;
      --paper: #edf3ef;
      --panel: #ffffff;
      --ink: #182027;
      --muted: #6b7982;
      --line: #d6dfda;
      --green: #2f8f72;
      --blue: #2c6f9f;
      --amber: #c68a2f;
      --red: #c9574b;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: #dfe8e3;
      font-family: "EB Garamond", Georgia, "Times New Roman", serif;
      color: var(--ink);
      overflow: hidden;
    }
    .poster {
      width: 1600px;
      height: 900px;
      margin: 0 auto;
      display: grid;
      grid-template-columns: 250px minmax(0, 1fr);
      overflow: hidden;
      background: var(--paper);
      border: 1px solid #c7d4cd;
      box-shadow: 0 28px 90px rgba(23, 33, 38, .18);
      transform-origin: top center;
    }
    .rail {
      background: var(--charcoal);
      color: #edf6f2;
      padding: 28px 22px;
      display: grid;
      grid-template-rows: auto auto 1fr auto;
      gap: 24px;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 20px;
      font-weight: 900;
    }
    .mark {
      width: 38px;
      height: 38px;
      display: grid;
      place-items: center;
      border-radius: 8px;
      background: #fff;
      color: var(--charcoal);
      font-size: 14px;
      font-weight: 950;
    }
    .rail-label {
      display: block;
      color: rgba(237,246,242,.54);
      font-size: 11px;
      font-weight: 900;
      text-transform: uppercase;
      letter-spacing: .09em;
      margin-bottom: 10px;
    }
    .chip {
      display: flex;
      justify-content: space-between;
      align-items: center;
      min-height: 36px;
      border: 1px solid rgba(255,255,255,.18);
      border-radius: 6px;
      padding: 0 10px;
      margin-bottom: 8px;
      color: rgba(237,246,242,.88);
      background: rgba(255,255,255,.04);
      font-size: 12px;
    }
    .chip::after {
      content: "";
      width: 7px;
      height: 7px;
      border-right: 1px solid rgba(255,255,255,.72);
      border-bottom: 1px solid rgba(255,255,255,.72);
      transform: rotate(45deg);
      margin-bottom: 3px;
    }
    .question strong {
      display: block;
      font-size: 25px;
      line-height: 1.05;
      margin-bottom: 12px;
    }
    .question p, .dataset p {
      margin: 0;
      color: rgba(237,246,242,.62);
      font-size: 13px;
      line-height: 1.55;
    }
    .dataset strong {
      display: block;
      font-size: 24px;
      margin-bottom: 5px;
    }
    .canvas {
      min-width: 0;
      min-height: 0;
      overflow: hidden;
      position: relative;
      padding: 24px;
      display: grid;
      grid-template-rows: 118px 100px 320px 278px;
      gap: 12px;
      align-content: start;
      background:
        linear-gradient(135deg, rgba(220,238,232,.9), rgba(237,243,239,0) 43%),
        var(--paper);
    }
    .top {
      min-height: 0;
      overflow: hidden;
      display: grid;
      grid-template-columns: minmax(0, 1fr) 390px;
      gap: 18px;
      align-items: center;
    }
    .eyebrow {
      color: var(--green);
      font-size: 12px;
      font-weight: 950;
      text-transform: uppercase;
      letter-spacing: .09em;
      margin-bottom: 6px;
    }
    h1 {
      margin: 0;
      font-size: 33px;
      line-height: 1;
      letter-spacing: 0;
    }
    .note {
      background: rgba(255,255,255,.78);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 13px 15px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.35;
    }
    .note strong {
      display: block;
      color: var(--ink);
      font-size: 15px;
      margin-bottom: 4px;
    }
    .signal-strip {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 13px;
      max-width: 820px;
    }
    .signal-strip span {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      min-height: 28px;
      padding: 6px 10px;
      border: 1px solid rgba(47,143,114,.18);
      border-radius: 999px;
      background: rgba(255,255,255,.58);
      color: var(--muted);
      font-size: 11px;
      box-shadow: 0 8px 18px rgba(32, 44, 50, .04);
    }
    .signal-strip strong {
      color: var(--green);
      font-weight: 950;
      white-space: nowrap;
    }
    .metric-strip {
      min-height: 0;
      height: 100%;
      overflow: hidden;
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 10px;
    }
    .metric-tile {
      position: relative;
      min-width: 0;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px 13px 11px;
      box-shadow: 0 10px 25px rgba(32, 44, 50, .06);
    }
    .metric-tile::before {
      content: "";
      position: absolute;
      inset: 0 auto 0 0;
      width: 4px;
      border-radius: 8px 0 0 8px;
      background: var(--green);
    }
    .metric-tile span {
      display: block;
      color: var(--muted);
      font-size: 11px;
      font-weight: 800;
      margin-bottom: 6px;
      padding-right: 54px;
    }
    .metric-tile strong {
      display: block;
      max-width: 100%;
      font-size: 20px;
      line-height: 1.02;
      overflow-wrap: anywhere;
    }
    .metric-tile p {
      position: absolute;
      top: 13px;
      right: 13px;
      margin: 0;
      font-size: 12px;
      font-weight: 950;
    }
    .metric-tile small {
      position: absolute;
      left: 13px;
      right: 13px;
      bottom: 9px;
      color: #8b9aa2;
      font-size: 10.5px;
    }
    .positive { color: var(--green); }
    .negative { color: var(--red); }
    .main-grid {
      min-height: 0;
      overflow: hidden;
      display: grid;
      grid-template-columns: 1.22fr .82fr;
      gap: 12px;
      align-items: stretch;
      height: 100%;
    }
    .bottom-grid {
      min-height: 0;
      overflow: hidden;
      display: grid;
      grid-template-columns: .85fr .95fr 1.2fr;
      gap: 12px;
      align-items: stretch;
      height: 100%;
    }
    .panel {
      min-width: 0;
      height: 100%;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 15px;
      overflow: hidden;
      box-shadow: 0 10px 25px rgba(32, 44, 50, .055);
    }
    .panel-head {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: start;
      margin-bottom: 8px;
    }
    h2 {
      margin: 0;
      font-size: 17px;
      line-height: 1.12;
    }
    .panel-note {
      color: #8d9aa4;
      font-size: 11px;
      text-align: right;
      line-height: 1.18;
    }
    svg {
      display: block;
      width: 100%;
      height: auto;
    }
    .axis { stroke: #dbe3df; stroke-width: 1; }
    .x-axis-label {
      fill: #7b8a82;
      font-size: 10px;
      font-weight: 850;
    }
    .area { fill: url(#revenueArea); }
    .revenue-line, .profit-line {
      fill: none;
      stroke-width: 3.4;
      stroke-linecap: round;
      stroke-linejoin: round;
    }
    .revenue-line { stroke: var(--green); }
    .profit-line { stroke: var(--blue); }
    .trend-svg {
      height: 232px;
    }
    .ticks {
      display: grid;
      grid-template-columns: repeat(18, 1fr);
      color: #95a29a;
      font-size: 9.5px;
      margin: 3px 18px 0;
    }
    .chart-legend {
      display: flex;
      gap: 12px;
      margin-top: 7px;
      color: var(--muted);
      font-size: 11px;
    }
    .legend-key {
      display: inline-block;
      width: 8px;
      height: 8px;
      border-radius: 50%;
      margin-right: 5px;
    }
    .rank-row {
      display: flex;
      gap: 9px;
      align-items: center;
      margin: 6px 0;
    }
    .rank-number {
      width: 23px;
      height: 23px;
      display: grid;
      place-items: center;
      border-radius: 6px;
      background: #edf3ef;
      color: var(--green);
      font-size: 11px;
      font-weight: 950;
    }
    .rank-main { flex: 1; min-width: 0; }
    .rank-label {
      display: flex;
      justify-content: space-between;
      gap: 9px;
      margin-bottom: 4px;
      font-size: 11px;
    }
    .rank-label span {
      color: var(--muted);
      font-weight: 800;
    }
    .rank-meta {
      display: flex;
      gap: 8px;
      color: #8d9aa4;
      font-size: 9.5px;
      margin-bottom: 4px;
    }
    .bar-track, .channel-track {
      height: 6px;
      border-radius: 999px;
      overflow: hidden;
      background: #edf2ef;
    }
    .bar-fill, .channel-track div {
      height: 100%;
      border-radius: 999px;
      background: linear-gradient(90deg, var(--green), var(--blue));
    }
    .channel-row { margin: 10px 0; }
    .channel-label {
      display: flex;
      justify-content: space-between;
      gap: 9px;
      margin-bottom: 5px;
      font-size: 12px;
    }
    .channel-label span {
      color: var(--muted);
      font-weight: 850;
    }
    .channel-row small {
      display: block;
      color: #8d9aa4;
      margin-top: 5px;
      font-size: 10px;
    }
    .customer-bars {
      display: flex;
      justify-content: space-between;
      align-items: end;
      gap: 7px;
      min-height: 150px;
    }
    .customer-month {
      flex: 1;
      text-align: center;
      color: var(--muted);
      font-size: 10px;
    }
    .stack {
      height: 138px;
      display: flex;
      flex-direction: column-reverse;
      justify-content: flex-start;
      gap: 2px;
      margin-bottom: 5px;
    }
    .stack span {
      display: block;
      border-radius: 4px 4px 0 0;
    }
    .stack .new { background: var(--blue); }
    .stack .repeat { background: var(--green); }
    .customer-month small {
      color: var(--red);
      display: block;
      margin-top: 1px;
    }
    .quality-panel {
      height: calc(100% - 30px);
      display: grid;
      grid-template-rows: 52px minmax(0, 1fr) 18px;
      gap: 8px;
    }
    .quality-summary {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }
    .quality-summary div {
      border: 1px solid var(--line);
      border-radius: 7px;
      background: #f6faf7;
      padding: 7px 8px;
    }
    .quality-summary span {
      display: block;
      color: var(--muted);
      font-size: 9.5px;
      font-weight: 850;
      margin-bottom: 2px;
    }
    .quality-summary strong {
      display: inline-block;
      font-size: 17px;
      line-height: 1;
      margin-right: 5px;
    }
    .quality-summary small {
      color: #8d9aa4;
      font-size: 9px;
      white-space: nowrap;
    }
    .quality-chart {
      min-height: 0;
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 7px;
      align-items: end;
    }
    .quality-month {
      min-width: 0;
      text-align: center;
      color: var(--muted);
      font-size: 9px;
    }
    .active-count {
      display: block;
      color: var(--ink);
      font-size: 10px;
      font-weight: 900;
      margin-bottom: 3px;
    }
    .quality-stack {
      height: 112px;
      display: flex;
      flex-direction: column-reverse;
      justify-content: flex-start;
      gap: 2px;
      align-items: stretch;
      border-bottom: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(47,143,114,.05), rgba(44,111,159,.05));
      border-radius: 5px 5px 0 0;
      overflow: hidden;
      margin-bottom: 4px;
    }
    .quality-stack span {
      display: block;
      border-radius: 4px 4px 0 0;
    }
    .quality-stack .repeat { background: var(--green); }
    .quality-stack .new { background: var(--blue); }
    .quality-month strong {
      display: block;
      color: var(--ink);
      font-size: 10px;
      line-height: 1;
    }
    .quality-month small {
      display: block;
      color: var(--red);
      font-size: 8.5px;
      margin-top: 2px;
      white-space: nowrap;
    }
    .quality-legend {
      display: flex;
      align-items: center;
      gap: 10px;
      color: var(--muted);
      font-size: 10px;
    }
    .quality-note {
      margin-left: auto;
      color: #8d9aa4;
    }
    .scatter .bubble-number {
      fill: #fff;
      font-size: 11px;
      font-weight: 950;
    }
    .scatter .axis-tick {
      fill: #8d9aa4;
      font-size: 9px;
      font-weight: 850;
    }
    .scatter-label {
      fill: #8d9aa4;
      font-size: 10px;
      font-weight: 800;
    }
    .risk-legend {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 3px 8px;
      margin-top: 3px;
    }
    .risk-key-row {
      display: grid;
      grid-template-columns: 16px minmax(0, 1fr);
      gap: 5px;
      align-items: center;
      font-size: 9px;
      color: var(--muted);
    }
    .risk-key-row span {
      width: 15px;
      height: 15px;
      display: grid;
      place-items: center;
      border-radius: 5px;
      background: #edf3ef;
      color: var(--green);
      font-weight: 950;
    }
    .risk-key-row strong {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .risk-key-row em {
      display: none;
      grid-column: 2;
      margin-top: -4px;
      color: #8d9aa4;
      font-style: normal;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    @media (max-width: 1599px) {
      .poster {
        margin: 0;
        transform-origin: top left;
      }
    }
    @media (max-width: 1536px) {
      .poster { transform: scale(.96); }
    }
    @media (max-width: 1440px) {
      .poster { transform: scale(.9); }
    }
    @media (max-width: 1366px) {
      .poster { transform: scale(.854); }
    }
    @media (max-width: 1280px) {
      .poster { transform: scale(.8); }
    }
    @media (max-width: 1180px) {
      .poster { transform: scale(.7375); }
    }
    @media (max-width: 1100px) {
      .poster { transform: scale(.64); }
    }
    @media (max-width: 900px) {
      .poster {
        transform: scale(.56);
      }
    }
  </style>
</head>
<body>
  <main class="poster">
    <aside class="rail">
      <div class="brand"><span class="mark">KR</span><span>Kora Retail Group</span></div>
      <section>
        <span class="rail-label">Filters</span>
        <div class="chip"><span>All regions</span></div>
        <div class="chip"><span>Omnichannel</span></div>
        <div class="chip"><span>Jan 2025-Jun 2026</span></div>
        <div class="chip"><span>Executive view</span></div>
      </section>
      <section class="question">
        <span class="rail-label">Management Question</span>
        <strong>Where is growth leaking?</strong>
        <p>Review revenue quality, retention, return pressure, fulfilment risk, and category margin before scaling acquisition spend.</p>
      </section>
      <section class="dataset">
        <span class="rail-label">Data Model</span>
        <strong>$row_count rows</strong>
        <p>18 months across regions, channels, categories, campaigns, customers, support, returns, and fulfilment signals.</p>
      </section>
    </aside>

    <section class="canvas">
      <header class="top">
        <div>
          <div class="eyebrow">Closed Month Review | June 2026</div>
          <h1>Revenue Leakage Review</h1>
          <div class="signal-strip">$signal_pills</div>
        </div>
        <aside class="note">
          <strong>Analyst note</strong>
          Revenue is growing, but the decision is whether profit, repeat customers, returns, and fulfilment are improving together.
        </aside>
      </header>

      <section class="metric-strip">$metric_tiles</section>

      <section class="main-grid">
        <article class="panel">
          <div class="panel-head"><h2>Revenue and Profit Movement</h2><span class="panel-note">18 months | closed periods</span></div>
          <svg class="trend-svg" viewBox="0 0 720 246" role="img" aria-label="Revenue and gross profit trend chart">
            <defs>
              <linearGradient id="revenueArea" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stop-color="#2f8f72" stop-opacity=".20"></stop>
                <stop offset="100%" stop-color="#2f8f72" stop-opacity="0"></stop>
              </linearGradient>
            </defs>
            <line class="axis" x1="42" y1="168" x2="698" y2="168"></line>
            <line class="axis" x1="42" y1="120" x2="698" y2="120"></line>
            <line class="axis" x1="42" y1="72" x2="698" y2="72"></line>
            $trend_x_axis
            <polygon class="area" points="$revenue_area"></polygon>
            <polyline class="revenue-line" points="$revenue_points"></polyline>
            <polyline class="profit-line" points="$profit_points"></polyline>
            <circle cx="$peak_x" cy="$peak_y" r="5" fill="#fff" stroke="#c68a2f" stroke-width="3"></circle>
            <text x="$peak_label_x" y="$peak_label_y" fill="#8a5b15" font-size="12" font-weight="800">Peak: $peak_month</text>
            <circle cx="$latest_revenue_x" cy="$latest_revenue_y" r="6" fill="#fff" stroke="#2f8f72" stroke-width="3"></circle>
            <text x="$latest_revenue_label_x" y="$latest_revenue_label_y" fill="#236b55" font-size="12" font-weight="800">Jun close</text>
          </svg>
          <div class="chart-legend">
            <span><i class="legend-key" style="background:#2f8f72"></i>Revenue</span>
            <span><i class="legend-key" style="background:#2c6f9f"></i>Gross profit</span>
          </div>
        </article>

        <article class="panel">
          <div class="panel-head"><h2>Category Contribution</h2><span class="panel-note">revenue, margin, returns</span></div>
          $ranking_bars
        </article>
      </section>

      <section class="bottom-grid">
        <article class="panel">
          <div class="panel-head"><h2>Channel Economics</h2><span class="panel-note">latest month</span></div>
          $channel_bars
        </article>
        <article class="panel">
          <div class="panel-head"><h2>Customer Quality</h2><span class="panel-note">active base, repeat share, churn</span></div>
          $customer_quality_panel
        </article>
        <article class="panel">
          <div class="panel-head"><h2>Return Pressure vs Margin</h2><span class="panel-note">bubble size = revenue</span></div>
          <svg class="scatter" viewBox="0 0 650 240" role="img" aria-label="Margin and returns risk chart">
            <line class="axis" x1="64" y1="196" x2="604" y2="196"></line>
            <line class="axis" x1="64" y1="48" x2="64" y2="196"></line>
            <line class="axis" x1="334" y1="48" x2="334" y2="196" stroke-dasharray="5 6"></line>
            <line class="axis" x1="64" y1="122" x2="604" y2="122" stroke-dasharray="5 6"></line>
            <text class="axis-tick" x="56" y="200" text-anchor="end">16%</text>
            <text class="axis-tick" x="56" y="126" text-anchor="end">28%</text>
            <text class="axis-tick" x="56" y="52" text-anchor="end">40%</text>
            <text class="axis-tick" x="64" y="218" text-anchor="middle">2%</text>
            <text class="axis-tick" x="334" y="218" text-anchor="middle">6%</text>
            <text class="axis-tick" x="604" y="218" text-anchor="middle">10%</text>
            $risk_scatter
            <text class="scatter-label" x="64" y="236">Lower returns</text>
            <text class="scatter-label" x="516" y="236">Higher returns</text>
            <text class="scatter-label" x="68" y="36">Margin rate</text>
          </svg>
          <div class="risk-legend">$risk_legend</div>
        </article>
      </section>
    </section>
  </main>
</body>
</html>
"""
    )
    return template.substitute(
        row_count=f"{len(rows):,}",
        signal_pills=signal_pills,
        metric_tiles=metric_tiles,
        trend_x_axis=landscape_x_axis(),
        revenue_area=landscape_area_points(revenue_series),
        revenue_points=landscape_line_points(revenue_series),
        profit_points=landscape_line_points(profit_series),
        peak_x=f"{peak_x:.1f}",
        peak_y=f"{peak_y:.1f}",
        peak_label_x=f"{min(peak_x + 12, 590):.1f}",
        peak_label_y=f"{max(peak_y - 12, 18):.1f}",
        peak_month=MONTHS[peak_index],
        latest_revenue_x=f"{latest_x:.1f}",
        latest_revenue_y=f"{latest_y:.1f}",
        latest_revenue_label_x=f"{max(latest_x - 72, 24):.1f}",
        latest_revenue_label_y=f"{max(latest_y - 18, 18):.1f}",
        ranking_bars=ranking_bars(category_items),
        channel_bars=channel_share_bars(channel_items),
        customer_quality_panel=customer_quality_panel(rows),
        risk_scatter=risk_scatter(category_items),
        risk_legend=risk_legend(category_items),
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = generate_dataset()
    write_dataset(rows)
    loaded_rows = load_rows()
    summary = build_summary(loaded_rows)
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    DASHBOARD_PATH.write_text(build_html(loaded_rows, summary), encoding="utf-8")
    LANDSCAPE_PATH.write_text(build_landscape_html(loaded_rows, summary), encoding="utf-8")
    print(f"Wrote {DATA_PATH}")
    print(f"Wrote {SUMMARY_PATH}")
    print(f"Wrote {DASHBOARD_PATH}")
    print(f"Wrote {LANDSCAPE_PATH}")


if __name__ == "__main__":
    main()
