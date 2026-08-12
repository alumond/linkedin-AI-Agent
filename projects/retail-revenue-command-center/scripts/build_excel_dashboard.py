from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

try:
    import xlsxwriter
    from xlsxwriter.utility import xl_col_to_name
except ImportError as exc:
    raise SystemExit("XlsxWriter is required. Run: python3 -m pip install --target .vendor XlsxWriter") from exc

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parents[1]
DATA_PATH = ROOT / "data" / "retail_operations_kpis.csv"
SUMMARY_PATH = ROOT / "outputs" / "kpi_summary.json"
POSTER_IMAGE = REPO_ROOT / "assets" / "featured_retail_revenue_leakage_review.png"
OUTPUT_PATH = ROOT / "outputs" / "retail_revenue_leakage_dashboard.xlsx"

MONTHS = [
    "2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06",
    "2025-07", "2025-08", "2025-09", "2025-10", "2025-11", "2025-12",
    "2026-01", "2026-02", "2026-03", "2026-04", "2026-05", "2026-06",
]

PROJECT_LINK = "https://github.com/alumond/linkedin-AI-Agent/tree/main/projects/retail-revenue-command-center"
DATA_LINK = "https://github.com/alumond/linkedin-AI-Agent/blob/main/projects/retail-revenue-command-center/data/retail_operations_kpis.csv"

COLORS = {
    "navy": "#172126",
    "navy2": "#202C32",
    "paper": "#EDF3EF",
    "panel": "#FFFFFF",
    "ink": "#182027",
    "muted": "#6B7982",
    "line": "#D6DFDA",
    "green": "#2F8F72",
    "blue": "#2C6F9F",
    "amber": "#C68A2F",
    "red": "#C9574B",
    "pale": "#F6FAF7",
    "chip": "#E7F2EC",
}

NUMERIC_FIELDS = {
    "orders", "revenue_ngn", "cost_ngn", "gross_profit_ngn", "marketing_spend_ngn", "returns",
    "support_tickets", "new_customers", "repeat_customers", "churned_customers", "fulfillment_delay_hours",
    "stockout_risk_pct", "customer_satisfaction", "data_quality_flags",
}


def load_rows() -> list[dict[str, object]]:
    with DATA_PATH.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    for row in rows:
        for field in NUMERIC_FIELDS:
            row[field] = float(row[field])
    return rows


def n(row: dict[str, object], key: str) -> float:
    return float(row[key])


def rows_for_month(rows: list[dict[str, object]], month: str) -> list[dict[str, object]]:
    return [row for row in rows if row["month"] == month]


def sum_field(rows: list[dict[str, object]], key: str) -> float:
    return sum(n(row, key) for row in rows)


def weighted_average(rows: list[dict[str, object]], value_key: str, weight_key: str = "orders") -> float:
    weight = sum_field(rows, weight_key)
    return sum(n(row, value_key) * n(row, weight_key) for row in rows) / weight if weight else 0.0


def aggregate_by(rows: list[dict[str, object]], dimension: str) -> dict[str, dict[str, float]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row[dimension])].append(row)
    result: dict[str, dict[str, float]] = {}
    for key, items in grouped.items():
        orders = sum_field(items, "orders")
        revenue = sum_field(items, "revenue_ngn")
        profit = sum_field(items, "gross_profit_ngn")
        returns = sum_field(items, "returns")
        new_customers = sum_field(items, "new_customers")
        repeat_customers = sum_field(items, "repeat_customers")
        active_customers = new_customers + repeat_customers
        result[key] = {
            "orders": orders,
            "revenue": revenue,
            "profit": profit,
            "margin": profit / revenue if revenue else 0.0,
            "return_rate": returns / orders if orders else 0.0,
            "repeat_rate": repeat_customers / active_customers if active_customers else 0.0,
            "delay": weighted_average(items, "fulfillment_delay_hours"),
            "stockout": weighted_average(items, "stockout_risk_pct"),
            "satisfaction": weighted_average(items, "customer_satisfaction"),
        }
    return result


def compact_money(value: float) -> str:
    if abs(value) >= 1_000_000_000:
        return f"NGN {value / 1_000_000_000:.2f}B"
    if abs(value) >= 1_000_000:
        return f"NGN {value / 1_000_000:.1f}M"
    return f"NGN {value:,.0f}"


def compact_count(value: float) -> str:
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if abs(value) >= 1_000:
        return f"{value / 1_000:.1f}K"
    return f"{value:,.0f}"


def delta(current: float, previous: float) -> float:
    return (current - previous) / previous if previous else 0.0


def add_formats(workbook: xlsxwriter.Workbook) -> dict[str, object]:
    font = "EB Garamond"
    body = "EB Garamond"
    return {
        "title": workbook.add_format({"font_name": font, "font_size": 28, "bold": True, "font_color": COLORS["ink"], "valign": "vcenter"}),
        "eyebrow": workbook.add_format({"font_name": body, "font_size": 10, "bold": True, "font_color": COLORS["green"]}),
        "body": workbook.add_format({"font_name": body, "font_size": 10, "font_color": COLORS["ink"]}),
        "muted": workbook.add_format({"font_name": body, "font_size": 9, "font_color": COLORS["muted"]}),
        "note_title": workbook.add_format({"font_name": body, "font_size": 13, "bold": True, "font_color": COLORS["ink"], "bg_color": COLORS["panel"], "top": 1, "bottom": 0, "left": 1, "right": 1, "border_color": COLORS["line"]}),
        "note": workbook.add_format({"font_name": body, "font_size": 10, "font_color": COLORS["muted"], "bg_color": COLORS["panel"], "text_wrap": True, "top": 0, "bottom": 1, "left": 1, "right": 1, "border_color": COLORS["line"]}),
        "rail": workbook.add_format({"bg_color": COLORS["navy"], "font_name": body, "font_color": "#EDF6F2"}),
        "rail_title": workbook.add_format({"bg_color": COLORS["navy"], "font_name": font, "font_size": 17, "bold": True, "font_color": "#EDF6F2", "valign": "vcenter"}),
        "rail_label": workbook.add_format({"bg_color": COLORS["navy"], "font_name": body, "font_size": 9, "bold": True, "font_color": "#9EABA8"}),
        "rail_big": workbook.add_format({"bg_color": COLORS["navy"], "font_name": font, "font_size": 23, "bold": True, "font_color": "#EDF6F2", "text_wrap": True, "valign": "top"}),
        "rail_text": workbook.add_format({"bg_color": COLORS["navy"], "font_name": body, "font_size": 11, "font_color": "#B6C1BD", "text_wrap": True, "valign": "top"}),
        "chip": workbook.add_format({"font_name": body, "font_size": 9, "font_color": COLORS["green"], "bg_color": COLORS["panel"], "border": 1, "border_color": COLORS["line"], "align": "center", "valign": "vcenter"}),
        "chip_strong": workbook.add_format({"font_name": body, "font_size": 9, "bold": True, "font_color": COLORS["green"], "bg_color": COLORS["panel"], "border": 1, "border_color": COLORS["line"], "align": "center", "valign": "vcenter"}),
        "kpi_label": workbook.add_format({"font_name": body, "font_size": 9, "bold": True, "font_color": COLORS["muted"], "bg_color": COLORS["panel"], "top": 1, "left": 1, "right": 1, "border_color": COLORS["line"]}),
        "kpi_value": workbook.add_format({"font_name": font, "font_size": 19, "bold": True, "font_color": COLORS["ink"], "bg_color": COLORS["panel"], "left": 1, "right": 1, "border_color": COLORS["line"], "valign": "vcenter"}),
        "kpi_delta": workbook.add_format({"font_name": body, "font_size": 10, "bold": True, "font_color": COLORS["green"], "bg_color": COLORS["panel"], "top": 1, "right": 1, "border_color": COLORS["line"], "align": "right"}),
        "kpi_note": workbook.add_format({"font_name": body, "font_size": 8, "font_color": COLORS["muted"], "bg_color": COLORS["panel"], "bottom": 1, "left": 1, "right": 1, "border_color": COLORS["line"]}),
        "accent": workbook.add_format({"bg_color": COLORS["green"], "top": 1, "bottom": 1, "left": 1, "border_color": COLORS["green"]}),
        "panel_title": workbook.add_format({"font_name": font, "font_size": 14, "bold": True, "font_color": COLORS["ink"], "bg_color": COLORS["panel"], "top": 1, "left": 1, "border_color": COLORS["line"]}),
        "panel_note": workbook.add_format({"font_name": body, "font_size": 9, "font_color": COLORS["muted"], "bg_color": COLORS["panel"], "top": 1, "right": 1, "border_color": COLORS["line"], "align": "right"}),
        "panel": workbook.add_format({"bg_color": COLORS["panel"], "border": 1, "border_color": COLORS["line"]}),
        "rank_num": workbook.add_format({"font_name": body, "font_size": 10, "bold": True, "font_color": COLORS["green"], "bg_color": COLORS["chip"], "align": "center", "valign": "vcenter"}),
        "label": workbook.add_format({"font_name": body, "font_size": 10, "bold": True, "font_color": COLORS["ink"], "bg_color": COLORS["panel"]}),
        "small": workbook.add_format({"font_name": body, "font_size": 8, "font_color": COLORS["muted"], "bg_color": COLORS["panel"]}),
        "currency": workbook.add_format({"font_name": body, "font_size": 9, "font_color": COLORS["muted"], "num_format": "#,##0,,.0\\M", "bg_color": COLORS["panel"], "align": "right"}),
        "pct": workbook.add_format({"font_name": body, "font_size": 8, "font_color": COLORS["muted"], "num_format": "0.0%", "bg_color": COLORS["panel"]}),
        "table_header": workbook.add_format({"font_name": body, "font_size": 9, "bold": True, "font_color": "#FFFFFF", "bg_color": COLORS["navy2"], "border": 1, "border_color": COLORS["navy2"]}),
        "table_text": workbook.add_format({"font_name": body, "font_size": 9, "font_color": COLORS["ink"], "border": 1, "border_color": COLORS["line"]}),
        "table_num": workbook.add_format({"font_name": body, "font_size": 9, "font_color": COLORS["ink"], "border": 1, "border_color": COLORS["line"], "num_format": "#,##0"}),
        "table_money": workbook.add_format({"font_name": body, "font_size": 9, "font_color": COLORS["ink"], "border": 1, "border_color": COLORS["line"], "num_format": "#,##0"}),
        "table_pct": workbook.add_format({"font_name": body, "font_size": 9, "font_color": COLORS["ink"], "border": 1, "border_color": COLORS["line"], "num_format": "0.0%"}),
        "model_header": workbook.add_format({"font_name": body, "font_size": 10, "bold": True, "font_color": COLORS["ink"], "bg_color": COLORS["chip"], "border": 1, "border_color": COLORS["line"]}),
        "model_cell": workbook.add_format({"font_name": body, "font_size": 9, "font_color": COLORS["ink"], "border": 1, "border_color": COLORS["line"]}),
        "model_money": workbook.add_format({"font_name": body, "font_size": 9, "font_color": COLORS["ink"], "num_format": "#,##0", "border": 1, "border_color": COLORS["line"]}),
        "model_pct": workbook.add_format({"font_name": body, "font_size": 9, "font_color": COLORS["ink"], "num_format": "0.0%", "border": 1, "border_color": COLORS["line"]}),
    }


def setup_sheet(sheet, widths: list[float], rows: int = 46) -> None:
    sheet.hide_gridlines(2)
    sheet.set_zoom(70)
    for index, width in enumerate(widths):
        sheet.set_column(index, index, width)
    for row in range(rows):
        sheet.set_row(row, 20)


def write_data_sheet(workbook, rows, fmts):
    ws = workbook.add_worksheet("Data")
    ws.hide_gridlines(2)
    headers = list(rows[0].keys())
    data = [[row[h] for h in headers] for row in rows]
    ws.write_row(0, 0, headers, fmts["table_header"])
    for r, row in enumerate(data, start=1):
        for c, value in enumerate(row):
            header = headers[c]
            if header in NUMERIC_FIELDS:
                fmt = fmts["table_money"] if header.endswith("_ngn") else fmts["table_num"]
                if header.endswith("_pct"):
                    fmt = fmts["table_pct"]
                ws.write(r, c, value, fmt)
            else:
                ws.write(r, c, value, fmts["table_text"])
    ws.add_table(0, 0, len(rows), len(headers) - 1, {
        "name": "RetailData",
        "style": "Table Style Medium 4",
        "columns": [{"header": h} for h in headers],
    })
    ws.freeze_panes(1, 4)
    widths = {
        "month": 10, "quarter": 10, "region": 15, "channel": 14, "category": 18, "campaign": 14,
        "orders": 10, "revenue_ngn": 15, "cost_ngn": 15, "gross_profit_ngn": 16,
        "marketing_spend_ngn": 18, "returns": 10, "support_tickets": 14,
        "new_customers": 14, "repeat_customers": 16, "churned_customers": 17,
        "fulfillment_delay_hours": 21, "stockout_risk_pct": 18, "customer_satisfaction": 20,
        "data_quality_flags": 18,
    }
    for c, h in enumerate(headers):
        ws.set_column(c, c, widths.get(h, 12))
    return ws


def write_model_sheet(workbook, rows, summary, fmts):
    ws = workbook.add_worksheet("Model")
    ws.hide_gridlines(2)
    ws.set_tab_color(COLORS["green"])
    ws.set_column("A:A", 16)
    ws.set_column("B:F", 16)
    ws.set_column("H:M", 18)
    ws.set_column("O:T", 18)
    ws.set_column("V:AA", 18)

    latest = rows_for_month(rows, MONTHS[-1])
    previous = rows_for_month(rows, MONTHS[-2])
    category_items = sorted(aggregate_by(latest, "category").items(), key=lambda item: item[1]["revenue"], reverse=True)
    channel_items = sorted(aggregate_by(latest, "channel").items(), key=lambda item: item[1]["revenue"], reverse=True)

    ws.write("A1", "Monthly Trend", fmts["model_header"])
    trend_headers = ["Month", "Revenue", "Gross Profit", "Orders", "Active Customers"]
    ws.write_row("A2", trend_headers, fmts["model_header"])
    for idx, month in enumerate(MONTHS, start=3):
        month_rows = rows_for_month(rows, month)
        active = sum_field(month_rows, "new_customers") + sum_field(month_rows, "repeat_customers")
        ws.write(idx - 1, 0, month, fmts["model_cell"])
        ws.write_formula(idx - 1, 1, f'=SUMIFS(RetailData[revenue_ngn],RetailData[month],A{idx})', fmts["model_money"], sum_field(month_rows, "revenue_ngn"))
        ws.write_formula(idx - 1, 2, f'=SUMIFS(RetailData[gross_profit_ngn],RetailData[month],A{idx})', fmts["model_money"], sum_field(month_rows, "gross_profit_ngn"))
        ws.write_formula(idx - 1, 3, f'=SUMIFS(RetailData[orders],RetailData[month],A{idx})', fmts["model_cell"], sum_field(month_rows, "orders"))
        ws.write_formula(idx - 1, 4, f'=SUMIFS(RetailData[new_customers],RetailData[month],A{idx})+SUMIFS(RetailData[repeat_customers],RetailData[month],A{idx})', fmts["model_cell"], active)

    ws.write("H1", "KPI Summary", fmts["model_header"])
    ws.write_row("H2", ["Metric", "Current", "Prior", "Delta", "Note"], fmts["model_header"])
    metrics = [
        ("Revenue", sum_field(latest, "revenue_ngn"), sum_field(previous, "revenue_ngn"), "closed month"),
        ("Gross Profit", sum_field(latest, "gross_profit_ngn"), sum_field(previous, "gross_profit_ngn"), "margin quality"),
        ("Orders", sum_field(latest, "orders"), sum_field(previous, "orders"), "fulfilled orders"),
        ("Customers", sum_field(latest, "new_customers") + sum_field(latest, "repeat_customers"), sum_field(previous, "new_customers") + sum_field(previous, "repeat_customers"), "active customers"),
        ("Repeat Rate", sum_field(latest, "repeat_customers") / (sum_field(latest, "new_customers") + sum_field(latest, "repeat_customers")), sum_field(previous, "repeat_customers") / (sum_field(previous, "new_customers") + sum_field(previous, "repeat_customers")), "retention base"),
    ]
    for row_idx, (name, current, prior, note) in enumerate(metrics, start=3):
        ws.write(row_idx - 1, 7, name, fmts["model_cell"])
        value_fmt = fmts["model_pct"] if "Rate" in name else fmts["model_money"] if name in {"Revenue", "Gross Profit"} else fmts["model_cell"]
        ws.write(row_idx - 1, 8, current, value_fmt)
        ws.write(row_idx - 1, 9, prior, value_fmt)
        ws.write_formula(row_idx - 1, 10, f'=IF(J{row_idx}=0,0,(I{row_idx}-J{row_idx})/J{row_idx})', fmts["model_pct"], delta(current, prior))
        ws.write(row_idx - 1, 11, note, fmts["model_cell"])

    ws.write("H10", "Category Contribution", fmts["model_header"])
    ws.write_row("H11", ["Category", "Revenue", "Gross Profit", "Margin", "Return Rate", "Share"], fmts["model_header"])
    total_category_revenue = sum(item[1]["revenue"] for item in category_items)
    for row_offset, (category, metric) in enumerate(category_items, start=12):
        ws.write(row_offset - 1, 7, category, fmts["model_cell"])
        ws.write_formula(row_offset - 1, 8, f'=SUMIFS(RetailData[revenue_ngn],RetailData[month],"{MONTHS[-1]}",RetailData[category],H{row_offset})', fmts["model_money"], metric["revenue"])
        ws.write_formula(row_offset - 1, 9, f'=SUMIFS(RetailData[gross_profit_ngn],RetailData[month],"{MONTHS[-1]}",RetailData[category],H{row_offset})', fmts["model_money"], metric["profit"])
        ws.write_formula(row_offset - 1, 10, f'=IF(I{row_offset}=0,0,J{row_offset}/I{row_offset})', fmts["model_pct"], metric["margin"])
        ws.write_formula(row_offset - 1, 11, f'=IF(SUMIFS(RetailData[orders],RetailData[month],"{MONTHS[-1]}",RetailData[category],H{row_offset})=0,0,SUMIFS(RetailData[returns],RetailData[month],"{MONTHS[-1]}",RetailData[category],H{row_offset})/SUMIFS(RetailData[orders],RetailData[month],"{MONTHS[-1]}",RetailData[category],H{row_offset}))', fmts["model_pct"], metric["return_rate"])
        ws.write_formula(row_offset - 1, 12, f'=IF(SUM($I$12:$I$17)=0,0,I{row_offset}/SUM($I$12:$I$17))', fmts["model_pct"], metric["revenue"] / total_category_revenue if total_category_revenue else 0)

    ws.write("O1", "Channel Economics", fmts["model_header"])
    ws.write_row("O2", ["Channel", "Revenue", "Margin", "Repeat Rate", "Share"], fmts["model_header"])
    total_channel_revenue = sum(item[1]["revenue"] for item in channel_items)
    for row_offset, (channel, metric) in enumerate(channel_items, start=3):
        ws.write(row_offset - 1, 14, channel, fmts["model_cell"])
        ws.write_formula(row_offset - 1, 15, f'=SUMIFS(RetailData[revenue_ngn],RetailData[month],"{MONTHS[-1]}",RetailData[channel],O{row_offset})', fmts["model_money"], metric["revenue"])
        ws.write_formula(row_offset - 1, 16, f'=IF(P{row_offset}=0,0,SUMIFS(RetailData[gross_profit_ngn],RetailData[month],"{MONTHS[-1]}",RetailData[channel],O{row_offset})/P{row_offset})', fmts["model_pct"], metric["margin"])
        ws.write_formula(row_offset - 1, 17, f'=IF(SUMIFS(RetailData[new_customers],RetailData[month],"{MONTHS[-1]}",RetailData[channel],O{row_offset})+SUMIFS(RetailData[repeat_customers],RetailData[month],"{MONTHS[-1]}",RetailData[channel],O{row_offset})=0,0,SUMIFS(RetailData[repeat_customers],RetailData[month],"{MONTHS[-1]}",RetailData[channel],O{row_offset})/(SUMIFS(RetailData[new_customers],RetailData[month],"{MONTHS[-1]}",RetailData[channel],O{row_offset})+SUMIFS(RetailData[repeat_customers],RetailData[month],"{MONTHS[-1]}",RetailData[channel],O{row_offset})))', fmts["model_pct"], metric["repeat_rate"])
        ws.write_formula(row_offset - 1, 18, f'=IF(SUM($P$3:$P$6)=0,0,P{row_offset}/SUM($P$3:$P$6))', fmts["model_pct"], metric["revenue"] / total_channel_revenue if total_channel_revenue else 0)

    ws.write("O10", "Customer Quality", fmts["model_header"])
    ws.write_row("O11", ["Month", "New", "Repeat", "Active", "Repeat Share", "Churn Rate"], fmts["model_header"])
    for row_offset, month in enumerate(MONTHS[-6:], start=12):
        month_rows = rows_for_month(rows, month)
        new = sum_field(month_rows, "new_customers")
        repeat = sum_field(month_rows, "repeat_customers")
        churned = sum_field(month_rows, "churned_customers")
        active = new + repeat
        ws.write(row_offset - 1, 14, month, fmts["model_cell"])
        ws.write_formula(row_offset - 1, 15, f'=SUMIFS(RetailData[new_customers],RetailData[month],O{row_offset})', fmts["model_cell"], new)
        ws.write_formula(row_offset - 1, 16, f'=SUMIFS(RetailData[repeat_customers],RetailData[month],O{row_offset})', fmts["model_cell"], repeat)
        ws.write_formula(row_offset - 1, 17, f'=P{row_offset}+Q{row_offset}', fmts["model_cell"], active)
        ws.write_formula(row_offset - 1, 18, f'=IF(R{row_offset}=0,0,Q{row_offset}/R{row_offset})', fmts["model_pct"], repeat / active if active else 0)
        ws.write_formula(row_offset - 1, 19, f'=IF(R{row_offset}=0,0,SUMIFS(RetailData[churned_customers],RetailData[month],O{row_offset})/R{row_offset})', fmts["model_pct"], churned / active if active else 0)

    ws.write("V1", "Return Pressure vs Margin", fmts["model_header"])
    ws.write_row("V2", ["No.", "Category", "Return Rate", "Margin", "Revenue", "Bubble"], fmts["model_header"])
    for idx, (category, metric) in enumerate(category_items, start=1):
        row_offset = idx + 2
        ws.write(row_offset - 1, 21, idx, fmts["model_cell"])
        ws.write(row_offset - 1, 22, category, fmts["model_cell"])
        ws.write_formula(row_offset - 1, 23, f'=L{idx + 11}', fmts["model_pct"], metric["return_rate"])
        ws.write_formula(row_offset - 1, 24, f'=K{idx + 11}', fmts["model_pct"], metric["margin"])
        ws.write_formula(row_offset - 1, 25, f'=I{idx + 11}', fmts["model_money"], metric["revenue"])
        ws.write_formula(row_offset - 1, 26, f'=Z{row_offset}/MAX($Z$3:$Z$8)*35', fmts["model_cell"], metric["revenue"] / max(item[1]["revenue"] for item in category_items) * 35)

    ws.freeze_panes(2, 0)
    return ws, {"category_items": category_items, "channel_items": channel_items, "metrics": metrics}


def write_poster_sheet(workbook, fmts):
    ws = workbook.add_worksheet("Executive Dashboard")
    ws.hide_gridlines(2)
    if hasattr(ws, "hide_row_col_headers"):
        ws.hide_row_col_headers()
    ws.set_zoom(52)
    ws.set_tab_color(COLORS["navy"])
    ws.set_landscape()
    ws.fit_to_pages(1, 1)
    ws.set_margins(0, 0, 0, 0)
    canvas_fmt = workbook.add_format({"bg_color": COLORS["paper"]})
    for col in range(44):
        ws.set_column(col, col, 8.43)
    for row in range(31):
        ws.set_row(row, 15)
        for col in range(44):
            ws.write_blank(row, col, None, canvas_fmt)
    ws.print_area(0, 0, 30, 43)
    if POSTER_IMAGE.exists():
        ws.insert_image("A1", str(POSTER_IMAGE), {"x_offset": 0, "y_offset": 0, "x_scale": 0.52, "y_scale": 0.52})
    else:
        ws.merge_range("B2:H5", "Featured dashboard PNG not found. Run the LinkedIn dashboard builder first.", fmts["panel_title"])
    return ws


def write_dashboard_sheet(workbook, rows, summary, helpers, fmts):
    ws = workbook.add_worksheet("Native Chart Audit")
    ws.set_tab_color(COLORS["green"])
    setup_sheet(ws, [3, 12, 12, 12, 2, 11, 11, 11, 11, 2, 11, 11, 11, 11, 2, 11, 11, 11, 11, 2, 11, 11, 11, 11, 2, 11], 43)
    ws.set_landscape()
    ws.fit_to_pages(1, 1)
    ws.set_paper(9)
    ws.set_margins(0.2, 0.2, 0.2, 0.2)

    for row in range(43):
        ws.write_blank(row, 0, None, fmts["rail"])
        ws.write_blank(row, 1, None, fmts["rail"])
        ws.write_blank(row, 2, None, fmts["rail"])
        ws.write_blank(row, 3, None, fmts["rail"])
        for col in range(4, 26):
            ws.write_blank(row, col, None, workbook.add_format({"bg_color": COLORS["paper"]}))

    ws.merge_range("B2:D3", "KR   Kora Retail\nGroup", fmts["rail_title"])
    ws.write("B6", "FILTERS", fmts["rail_label"])
    filter_fmt = workbook.add_format({"font_name": "EB Garamond", "font_size": 10, "font_color": "#EDF6F2", "bg_color": COLORS["navy2"], "border": 1, "border_color": "#445159", "valign": "vcenter"})
    for row_index, text in zip([6, 8, 10, 12], ["All regions", "Omnichannel", "Jan 2025-Jun 2026", "Executive view"]):
        ws.merge_range(row_index, 1, row_index, 3, text, filter_fmt)
    ws.write("B16", "MANAGEMENT QUESTION", fmts["rail_label"])
    ws.merge_range("B18:D21", "Where is\ngrowth leaking?", fmts["rail_big"])
    ws.merge_range("B22:D27", "Review revenue quality, retention, return pressure, fulfillment risk, and category margin before scaling acquisition spend.", fmts["rail_text"])
    ws.write("B36", "DATA MODEL", fmts["rail_label"])
    ws.merge_range("B38:D39", "2,160 rows", fmts["rail_big"])
    ws.merge_range("B40:D43", "18 months across regions, channels, categories, campaigns, customers, support, returns, and fulfillment signals.", fmts["rail_text"])

    ws.write("F3", "CLOSED MONTH REVIEW | JUNE 2026", fmts["eyebrow"])
    ws.merge_range("F4:N5", "Revenue Leakage Review", fmts["title"])
    signal_fmt = fmts["chip"]
    ws.merge_range("F6:H6", "Profit quality holding   GP +8.3% vs revenue +8.8%", signal_fmt)
    ws.merge_range("I6:K6", "Returns contained   return rate 5.1%", signal_fmt)
    ws.merge_range("L6:N6", "Retention base   repeat share 60.2%", signal_fmt)
    ws.merge_range("S3:X3", "Analyst note", fmts["note_title"])
    ws.merge_range("S4:X6", "Revenue is growing, but the decision is whether profit, repeat customers, returns, and fulfillment are improving together.", fmts["note"])

    kpis = helpers["metrics"]
    kpi_blocks = [("F", "H"), ("J", "L"), ("N", "P"), ("R", "T"), ("V", "X")]
    for idx, (metric, current, prior, note) in enumerate(kpis):
        start_col = [5, 9, 13, 17, 21][idx]
        end_col = start_col + 2
        ws.write(8, start_col - 1, None, fmts["accent"])
        ws.write(9, start_col - 1, None, fmts["accent"])
        ws.write(10, start_col - 1, None, fmts["accent"])
        ws.merge_range(8, start_col, 8, end_col - 1, metric, fmts["kpi_label"])
        ws.write(8, end_col, delta(current, prior), fmts["kpi_delta"])
        if metric == "Revenue" or metric == "Gross Profit":
            display = compact_money(current)
        elif metric == "Repeat Rate":
            display = f"{current * 100:.1f}%"
        else:
            display = compact_count(current)
        ws.merge_range(9, start_col, 9, end_col, display, fmts["kpi_value"])
        ws.merge_range(10, start_col, 10, end_col, note, fmts["kpi_note"])

    # Revenue trend panel.
    ws.merge_range("F13:N13", "Revenue and Profit Movement", fmts["panel_title"])
    ws.merge_range("O13:P13", "18 months | closed periods", fmts["panel_note"])
    ws.conditional_format("F13:P27", {"type": "no_errors", "format": fmts["panel"]})
    trend_chart = workbook.add_chart({"type": "line"})
    trend_chart.add_series({"name": "='Model'!$B$2", "categories": "='Model'!$A$3:$A$20", "values": "='Model'!$B$3:$B$20", "line": {"color": COLORS["green"], "width": 2.75}})
    trend_chart.add_series({"name": "='Model'!$C$2", "categories": "='Model'!$A$3:$A$20", "values": "='Model'!$C$3:$C$20", "line": {"color": COLORS["blue"], "width": 2.75}})
    trend_chart.set_title({"none": True})
    trend_chart.set_legend({"position": "bottom"})
    trend_chart.set_x_axis({"num_font": {"color": COLORS["muted"], "name": "EB Garamond", "size": 8}, "major_tick_mark": "none", "line": {"color": COLORS["line"]}})
    trend_chart.set_y_axis({"num_format": "#,##0,,.0M", "num_font": {"color": COLORS["muted"], "name": "EB Garamond", "size": 8}, "major_gridlines": {"visible": True, "line": {"color": COLORS["line"], "transparency": 20}}, "line": {"color": COLORS["line"]}})
    trend_chart.set_chartarea({"border": {"none": True}, "fill": {"color": COLORS["panel"]}})
    trend_chart.set_plotarea({"border": {"none": True}, "fill": {"color": COLORS["panel"]}})
    ws.insert_chart("F14", trend_chart, {"x_scale": 1.33, "y_scale": 1.24})

    # Category contribution panel.
    ws.merge_range("R13:V13", "Category Contribution", fmts["panel_title"])
    ws.merge_range("W13:X13", "revenue, margin, returns", fmts["panel_note"])
    ws.conditional_format("R13:X27", {"type": "no_errors", "format": fmts["panel"]})
    cat_items = helpers["category_items"]
    max_rev = max(item[1]["revenue"] for item in cat_items)
    for item_index, (category, metric) in enumerate(cat_items):
        row_index = 14 + item_index * 2
        ws.write(row_index, 17, item_index + 1, fmts["rank_num"])
        ws.merge_range(row_index, 18, row_index, 20, category, fmts["label"])
        ws.merge_range(row_index, 21, row_index, 23, compact_money(metric["revenue"]), workbook.add_format({"font_name": "EB Garamond", "font_size": 10, "font_color": COLORS["muted"], "bold": True, "bg_color": COLORS["panel"], "align": "right"}))
        ws.merge_range(row_index + 1, 18, row_index + 1, 23, f"Margin {metric['margin'] * 100:.1f}%   Returns {metric['return_rate'] * 100:.1f}%", fmts["small"])
        ws.write(row_index + 1, 17, metric["revenue"] / max_rev, workbook.add_format({"bg_color": COLORS["panel"], "font_color": COLORS["panel"], "num_format": "0%"}))
    ws.conditional_format("R16:R27", {"type": "data_bar", "bar_color": COLORS["green"], "bar_solid": True, "bar_only": True, "min_type": "num", "min_value": 0, "max_type": "num", "max_value": 1})

    # Bottom panels.
    ws.merge_range("F30:I30", "Channel Economics", fmts["panel_title"])
    ws.write("J30", "latest month", fmts["panel_note"])
    ws.conditional_format("F30:J41", {"type": "no_errors", "format": fmts["panel"]})
    channel_items = helpers["channel_items"]
    max_ch = max(item[1]["revenue"] for item in channel_items)
    for item_index, (channel, metric) in enumerate(channel_items):
        row_index = 31 + item_index * 3
        ws.write(row_index, 5, channel, fmts["label"])
        ws.merge_range(row_index, 7, row_index, 9, compact_money(metric["revenue"]), workbook.add_format({"font_name": "EB Garamond", "font_size": 10, "font_color": COLORS["muted"], "bold": True, "bg_color": COLORS["panel"], "align": "right"}))
        ws.write(row_index + 1, 5, metric["revenue"] / max_ch, workbook.add_format({"bg_color": COLORS["panel"], "font_color": COLORS["panel"], "num_format": "0%"}))
        ws.merge_range(row_index + 2, 5, row_index + 2, 9, f"Margin {metric['margin'] * 100:.1f}% | Repeat {metric['repeat_rate'] * 100:.1f}%", fmts["small"])
    ws.conditional_format("F33:F42", {"type": "data_bar", "bar_color": COLORS["blue"], "bar_solid": True, "bar_only": True, "min_type": "num", "min_value": 0, "max_type": "num", "max_value": 1})

    ws.merge_range("L30:O30", "Customer Quality", fmts["panel_title"])
    ws.write("P30", "repeat share, churn", fmts["panel_note"])
    ws.conditional_format("L30:P41", {"type": "no_errors", "format": fmts["panel"]})
    latest_repeat = helpers["metrics"][4][1]
    latest_churn = sum_field(rows_for_month(rows, MONTHS[-1]), "churned_customers") / (sum_field(rows_for_month(rows, MONTHS[-1]), "new_customers") + sum_field(rows_for_month(rows, MONTHS[-1]), "repeat_customers"))
    ws.merge_range("L32:M33", f"Repeat share\n{latest_repeat * 100:.1f}%", workbook.add_format({"font_name": "EB Garamond", "font_size": 11, "bold": True, "font_color": COLORS["ink"], "bg_color": COLORS["pale"], "border": 1, "border_color": COLORS["line"], "text_wrap": True, "valign": "vcenter"}))
    ws.merge_range("O32:P33", f"Churn pressure\n{latest_churn * 100:.1f}%", workbook.add_format({"font_name": "EB Garamond", "font_size": 11, "bold": True, "font_color": COLORS["ink"], "bg_color": COLORS["pale"], "border": 1, "border_color": COLORS["line"], "text_wrap": True, "valign": "vcenter"}))
    cust_chart = workbook.add_chart({"type": "column", "subtype": "stacked"})
    cust_chart.add_series({"name": "='Model'!$P$11", "categories": "='Model'!$O$12:$O$17", "values": "='Model'!$P$12:$P$17", "fill": {"color": COLORS["blue"]}, "border": {"color": COLORS["blue"]}})
    cust_chart.add_series({"name": "='Model'!$Q$11", "categories": "='Model'!$O$12:$O$17", "values": "='Model'!$Q$12:$Q$17", "fill": {"color": COLORS["green"]}, "border": {"color": COLORS["green"]}})
    cust_chart.set_title({"none": True})
    cust_chart.set_legend({"position": "bottom"})
    cust_chart.set_y_axis({"visible": False, "major_gridlines": {"visible": False}})
    cust_chart.set_x_axis({"num_font": {"name": "EB Garamond", "size": 8, "color": COLORS["muted"]}, "line": {"color": COLORS["line"]}})
    cust_chart.set_chartarea({"border": {"none": True}, "fill": {"color": COLORS["panel"]}})
    cust_chart.set_plotarea({"border": {"none": True}, "fill": {"color": COLORS["panel"]}})
    ws.insert_chart("L34", cust_chart, {"x_scale": 0.84, "y_scale": 0.74})

    ws.merge_range("R30:V30", "Return Pressure vs Margin", fmts["panel_title"])
    ws.merge_range("W30:X30", "bubble size = revenue", fmts["panel_note"])
    ws.conditional_format("R30:X41", {"type": "no_errors", "format": fmts["panel"]})
    bubble_chart = workbook.add_chart({"type": "scatter"})
    colors = [COLORS["red"], "#F2B544", "#F2B544", COLORS["red"], "#F2B544", "#2BB3A3"]
    for idx in range(6):
        row = idx + 3
        marker_size = 8 + int(cat_items[idx][1]["revenue"] / max(item[1]["revenue"] for item in cat_items) * 14)
        bubble_chart.add_series({
            "name": f"='Model'!$V${row}",
            "categories": f"='Model'!$X${row}:$X${row}",
            "values": f"='Model'!$Y${row}:$Y${row}",
            "marker": {"type": "circle", "size": marker_size, "fill": {"color": colors[idx], "transparency": 10}, "border": {"none": True}},
            "line": {"none": True},
            "data_labels": {"value": False, "series_name": True, "font": {"name": "EB Garamond", "size": 8, "color": "#FFFFFF", "bold": True}},
        })
    bubble_chart.set_title({"none": True})
    bubble_chart.set_legend({"none": True})
    bubble_chart.set_x_axis({"min": 0.02, "max": 0.10, "num_format": "0%", "name": "Return rate", "name_font": {"name": "EB Garamond", "size": 8, "color": COLORS["muted"]}, "num_font": {"name": "EB Garamond", "size": 8, "color": COLORS["muted"]}, "major_gridlines": {"visible": True, "line": {"color": COLORS["line"], "dash_type": "dash"}}, "line": {"color": COLORS["line"]}})
    bubble_chart.set_y_axis({"min": 0.16, "max": 0.40, "num_format": "0%", "name": "Margin", "name_font": {"name": "EB Garamond", "size": 8, "color": COLORS["muted"]}, "num_font": {"name": "EB Garamond", "size": 8, "color": COLORS["muted"]}, "major_gridlines": {"visible": True, "line": {"color": COLORS["line"], "dash_type": "dash"}}, "line": {"color": COLORS["line"]}})
    bubble_chart.set_chartarea({"border": {"none": True}, "fill": {"color": COLORS["panel"]}})
    bubble_chart.set_plotarea({"border": {"none": True}, "fill": {"color": COLORS["panel"]}})
    ws.insert_chart("R32", bubble_chart, {"x_scale": 0.96, "y_scale": 0.74})
    for idx, (category, _) in enumerate(cat_items, start=1):
        row = 40 + (idx - 1) // 3
        col = 17 + ((idx - 1) % 3) * 3
        ws.write(row, col, idx, fmts["rank_num"])
        ws.merge_range(row, col + 1, row, col + 2, category, fmts["small"])

    ws.write_url("F43", PROJECT_LINK, fmts["small"], "GitHub project and data")
    ws.hide()
    return ws


def write_sources_sheet(workbook, fmts):
    ws = workbook.add_worksheet("Source Notes")
    ws.hide_gridlines(2)
    ws.set_column("A:A", 24)
    ws.set_column("B:B", 110)
    ws.write("A1", "Source", fmts["model_header"])
    ws.write("B1", "Detail", fmts["model_header"])
    rows = [
        ("Project", PROJECT_LINK),
        ("Dataset", DATA_LINK),
        ("Workbook note", "The dashboard uses a synthetic retail operations dataset generated by the Python project builder. Data is for portfolio demonstration and executive-dashboard design practice."),
        ("Design note", "LinkedIn Poster preserves the exact 16:9 dashboard image. Executive Dashboard rebuilds the story using native Excel cells, charts, formulas, and conditional formatting."),
    ]
    for idx, (source, detail) in enumerate(rows, start=2):
        ws.write(idx - 1, 0, source, fmts["model_cell"])
        if detail.startswith("http"):
            ws.write_url(idx - 1, 1, detail, fmts["model_cell"], detail)
        else:
            ws.write(idx - 1, 1, detail, fmts["model_cell"])


def main() -> None:
    rows = load_rows()
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8")) if SUMMARY_PATH.exists() else {}
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    workbook = xlsxwriter.Workbook(str(OUTPUT_PATH))
    workbook.set_properties({
        "title": "Retail Revenue Leakage Review Excel Dashboard",
        "subject": "Executive retail analytics dashboard",
        "author": "Almond Owolabi",
        "comments": "Generated from the retail revenue command center project.",
    })
    fmts = add_formats(workbook)
    poster_ws = write_poster_sheet(workbook, fmts)
    write_data_sheet(workbook, rows, fmts)
    model_ws, helpers = write_model_sheet(workbook, rows, summary, fmts)
    write_dashboard_sheet(workbook, rows, summary, helpers, fmts)
    poster_ws.activate()
    poster_ws.set_first_sheet()
    write_sources_sheet(workbook, fmts)
    workbook.close()
    print(f"Wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
