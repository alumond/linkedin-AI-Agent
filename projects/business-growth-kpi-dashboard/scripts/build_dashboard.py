from __future__ import annotations

import csv
import html
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "monthly_growth_kpis.csv"
OUTPUT_DIR = ROOT / "outputs"
SUMMARY_PATH = OUTPUT_DIR / "kpi_summary.json"
DASHBOARD_PATH = OUTPUT_DIR / "dashboard.html"


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def money(value: float) -> str:
    return f"${value:,.0f}"


def growth(current: float, previous: float) -> float:
    if previous == 0:
        return 0.0
    return (current - previous) / previous


def load_rows() -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    with DATA_PATH.open(newline="", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for raw in reader:
            row: dict[str, float | str] = {"month": raw["month"]}
            for key, value in raw.items():
                if key != "month":
                    row[key] = float(value)
            rows.append(row)
    return rows


def enrich(rows: list[dict[str, float | str]]) -> list[dict[str, float | str]]:
    enriched: list[dict[str, float | str]] = []
    previous_paid = 0.0
    previous_revenue = 0.0
    for row in rows:
        visitors = float(row["website_visitors"])
        trials = float(row["trial_signups"])
        paid = float(row["paid_customers"])
        churned = float(row["churned_customers"])
        revenue = float(row["revenue_usd"])
        spend = float(row["marketing_spend_usd"])
        new_paid = max(paid - previous_paid + churned, 0.0)
        enriched_row = dict(row)
        enriched_row["visitor_to_trial_rate"] = trials / visitors
        enriched_row["trial_to_paid_rate"] = new_paid / trials if trials else 0.0
        enriched_row["churn_rate"] = churned / previous_paid if previous_paid else 0.0
        enriched_row["revenue_growth_rate"] = growth(revenue, previous_revenue) if previous_revenue else 0.0
        enriched_row["customer_acquisition_cost"] = spend / new_paid if new_paid else 0.0
        enriched_row["new_paid_customers"] = new_paid
        enriched.append(enriched_row)
        previous_paid = paid
        previous_revenue = revenue
    return enriched


def trend(values: list[float]) -> str:
    if len(values) < 2:
        return "flat"
    change = growth(values[-1], values[0])
    if change >= 0.10:
        return "improving"
    if change <= -0.10:
        return "declining"
    return "stable"


def points(values: list[float], width: int = 720, height: int = 180) -> str:
    low = min(values)
    high = max(values)
    span = high - low or 1
    step = width / (len(values) - 1)
    coords = []
    for index, value in enumerate(values):
        x = index * step
        y = height - ((value - low) / span * height)
        coords.append(f"{x:.1f},{y:.1f}")
    return " ".join(coords)


def build_summary(rows: list[dict[str, float | str]]) -> dict[str, object]:
    latest = rows[-1]
    first = rows[0]
    previous = rows[-2]
    summary = {
        "period": f"{first['month']} to {latest['month']}",
        "latest_month": latest["month"],
        "headline_metrics": {
            "revenue": money(float(latest["revenue_usd"])),
            "revenue_growth_mom": pct(float(latest["revenue_growth_rate"])),
            "paid_customers": int(float(latest["paid_customers"])),
            "paid_customer_growth_mom": pct(growth(float(latest["paid_customers"]), float(previous["paid_customers"]))),
            "trial_to_paid_rate": pct(float(latest["trial_to_paid_rate"])),
            "churn_rate": pct(float(latest["churn_rate"])),
            "reporting_hours": int(float(latest["reporting_hours"])),
            "data_quality_issues": int(float(latest["data_quality_issues"])),
        },
        "diagnosis": [
            "Revenue and paid customers are growing, but churn rose in the latest month.",
            "Reporting hours fell as dashboard usage increased, suggesting better self-service visibility.",
            "Data quality issues dropped across the period, which makes KPI review more reliable.",
        ],
        "recommendations": [
            "Investigate churn drivers before scaling acquisition spend further.",
            "Use the dashboard adoption trend as a case for retiring manual weekly reports.",
            "Create an owner for each core KPI: acquisition, conversion, retention, revenue, and data quality.",
        ],
    }
    return summary


def card(label: str, value: str, note: str) -> str:
    return f"""
      <section class="card">
        <p>{html.escape(label)}</p>
        <strong>{html.escape(value)}</strong>
        <span>{html.escape(note)}</span>
      </section>
    """


def build_html(rows: list[dict[str, float | str]], summary: dict[str, object]) -> str:
    latest = rows[-1]
    metrics = summary["headline_metrics"]
    assert isinstance(metrics, dict)
    revenue_points = points([float(row["revenue_usd"]) for row in rows])
    churn_points = points([float(row["churn_rate"]) for row in rows])
    dashboard_points = points([float(row["dashboard_users"]) for row in rows])
    table_rows = "\n".join(
        f"""
        <tr>
          <td>{html.escape(str(row["month"]))}</td>
          <td>{money(float(row["revenue_usd"]))}</td>
          <td>{int(float(row["paid_customers"]))}</td>
          <td>{pct(float(row["trial_to_paid_rate"]))}</td>
          <td>{pct(float(row["churn_rate"]))}</td>
          <td>{int(float(row["reporting_hours"]))}</td>
          <td>{int(float(row["data_quality_issues"]))}</td>
        </tr>
        """
        for row in rows[-6:]
    )
    diagnosis = "".join(f"<li>{html.escape(item)}</li>" for item in summary["diagnosis"])
    recommendations = "".join(f"<li>{html.escape(item)}</li>" for item in summary["recommendations"])
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Business Growth KPI Dashboard</title>
  <style>
    :root {{
      --ink: #17202a;
      --muted: #5b6773;
      --line: #d8dee4;
      --paper: #f7f3ea;
      --panel: #ffffff;
      --green: #107c41;
      --blue: #2563eb;
      --amber: #b45309;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      background: linear-gradient(135deg, #f7f3ea 0%, #eef5f3 48%, #f9fafb 100%);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 44px 22px 64px; }}
    header {{ display: grid; gap: 12px; margin-bottom: 28px; }}
    .eyebrow {{ color: var(--green); font-weight: 800; text-transform: uppercase; letter-spacing: .08em; font-size: 13px; }}
    h1 {{ margin: 0; font-size: clamp(34px, 5vw, 64px); line-height: 1; max-width: 850px; }}
    .lead {{ max-width: 760px; color: var(--muted); font-size: 18px; line-height: 1.55; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; margin: 30px 0; }}
    .card, .panel {{
      background: rgba(255,255,255,.86);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 20px 45px rgba(23,32,42,.07);
    }}
    .card {{ padding: 18px; }}
    .card p {{ margin: 0 0 10px; color: var(--muted); font-size: 13px; }}
    .card strong {{ display: block; font-size: 27px; line-height: 1.1; }}
    .card span {{ display: block; margin-top: 8px; color: var(--muted); font-size: 13px; line-height: 1.35; }}
    .panel {{ padding: 24px; margin-top: 18px; }}
    .panel h2 {{ margin: 0 0 14px; font-size: 22px; }}
    .charts {{ display: grid; grid-template-columns: 1.3fr .7fr; gap: 18px; }}
    svg {{ width: 100%; height: auto; overflow: visible; }}
    .axis {{ stroke: #cbd5e1; stroke-width: 1; }}
    .line {{ fill: none; stroke-width: 4; stroke-linecap: round; stroke-linejoin: round; }}
    .revenue {{ stroke: var(--blue); }}
    .churn {{ stroke: var(--amber); }}
    .users {{ stroke: var(--green); }}
    ul {{ margin: 0; padding-left: 20px; color: var(--muted); line-height: 1.7; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ padding: 12px 10px; border-bottom: 1px solid var(--line); text-align: left; }}
    th {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .06em; }}
    .tag {{ display: inline-block; margin: 0 8px 8px 0; padding: 7px 10px; border: 1px solid var(--line); border-radius: 999px; background: #fff; color: var(--muted); font-size: 13px; }}
    @media (max-width: 860px) {{
      .grid, .charts {{ grid-template-columns: 1fr; }}
      main {{ padding-top: 28px; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div class="eyebrow">Portfolio Project | Business Growth Analytics</div>
      <h1>Business Growth KPI Dashboard</h1>
      <p class="lead">A decision-support dashboard for tracking acquisition, conversion, retention, revenue, reporting efficiency, and data quality. Built to show how raw KPI data can become a weekly management conversation.</p>
    </header>

    <section class="grid">
      {card("Revenue", str(metrics["revenue"]), f"{metrics['revenue_growth_mom']} month over month")}
      {card("Paid customers", str(metrics["paid_customers"]), f"{metrics['paid_customer_growth_mom']} month over month")}
      {card("Trial to paid", str(metrics["trial_to_paid_rate"]), "latest month conversion")}
      {card("Churn", str(metrics["churn_rate"]), "latest month retention risk")}
    </section>

    <section class="charts">
      <article class="panel">
        <h2>Revenue trend</h2>
        <svg viewBox="0 0 720 210" role="img" aria-label="Revenue trend line chart">
          <line class="axis" x1="0" y1="190" x2="720" y2="190"></line>
          <polyline class="line revenue" points="{revenue_points}"></polyline>
        </svg>
      </article>
      <article class="panel">
        <h2>Operating signals</h2>
        <span class="tag">Dashboard users: {int(float(latest["dashboard_users"]))}</span>
        <span class="tag">Reporting hours: {int(float(latest["reporting_hours"]))}</span>
        <span class="tag">Data issues: {int(float(latest["data_quality_issues"]))}</span>
        <svg viewBox="0 0 720 210" role="img" aria-label="Churn and dashboard adoption trend lines">
          <line class="axis" x1="0" y1="190" x2="720" y2="190"></line>
          <polyline class="line churn" points="{churn_points}"></polyline>
          <polyline class="line users" points="{dashboard_points}"></polyline>
        </svg>
      </article>
    </section>

    <section class="panel">
      <h2>Diagnosis</h2>
      <ul>{diagnosis}</ul>
    </section>

    <section class="panel">
      <h2>Recommended management actions</h2>
      <ul>{recommendations}</ul>
    </section>

    <section class="panel">
      <h2>Last six months</h2>
      <table>
        <thead>
          <tr>
            <th>Month</th>
            <th>Revenue</th>
            <th>Paid customers</th>
            <th>Trial to paid</th>
            <th>Churn</th>
            <th>Reporting hours</th>
            <th>Data issues</th>
          </tr>
        </thead>
        <tbody>{table_rows}</tbody>
      </table>
    </section>
  </main>
</body>
</html>
"""


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = enrich(load_rows())
    summary = build_summary(rows)
    summary["trend_checks"] = {
        "revenue": trend([float(row["revenue_usd"]) for row in rows]),
        "paid_customers": trend([float(row["paid_customers"]) for row in rows]),
        "reporting_hours": trend([float(row["reporting_hours"]) for row in rows]),
        "data_quality_issues": trend([float(row["data_quality_issues"]) for row in rows]),
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    DASHBOARD_PATH.write_text(build_html(rows, summary), encoding="utf-8")
    print(f"Wrote {SUMMARY_PATH}")
    print(f"Wrote {DASHBOARD_PATH}")


if __name__ == "__main__":
    main()
