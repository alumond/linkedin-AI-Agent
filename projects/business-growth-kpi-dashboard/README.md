# Business Growth KPI Dashboard

This flagship portfolio project shows how raw operating data can become a weekly decision dashboard for a growth-focused team.

The goal is not to make a decorative chart. The goal is to answer management questions:

- Is revenue growing for the right reason?
- Are paid customers increasing faster than churn?
- Is reporting work going down as dashboard adoption rises?
- Are data quality issues improving enough to trust the KPIs?
- Which metric needs an owner this week?

## Business Problem

A growing digital business has monthly data across acquisition, trials, paid customers, churn, revenue, reporting workload, dashboard adoption, and data quality issues.

The team needs a simple KPI view that turns those numbers into decisions. Leadership does not need another spreadsheet. They need a clear read on growth, retention risk, reporting efficiency, and data reliability.

## Dataset

The dataset is a realistic sample operating dataset covering January 2025 to June 2026.

File: `data/monthly_growth_kpis.csv`

Fields include:

- website visitors
- trial signups
- paid customers
- churned customers
- revenue
- marketing spend
- support tickets
- reporting hours
- data quality issues
- dashboard users

## Tools Used

- Python
- CSV
- JSON
- HTML
- CSS
- SVG line charts

The project intentionally uses Python standard library only. That makes it easy to run in a clean environment without dependency issues.

## KPI Logic

The script calculates:

- visitor-to-trial conversion rate
- trial-to-paid conversion rate
- churn rate
- month-over-month revenue growth
- new paid customers
- customer acquisition cost
- trend direction for core signals

## Key Findings

- Revenue and paid customers improved across the period.
- Churn increased in the latest month, which means growth needs a retention check before more acquisition spend.
- Reporting hours dropped while dashboard users increased, suggesting stronger self-service visibility.
- Data quality issues declined, which improves confidence in KPI review.

## Business Recommendations

1. Investigate churn drivers before increasing marketing spend.
2. Assign clear owners for acquisition, conversion, retention, revenue, and data quality.
3. Retire manual weekly reporting where the dashboard already answers the same question.
4. Track dashboard adoption as an operations KPI, not just a usage metric.

## How To Run

From this project folder:

```bash
python3 scripts/build_dashboard.py
```

Outputs:

- `outputs/dashboard.html`
- `outputs/kpi_summary.json`

Open `outputs/dashboard.html` in a browser to view the dashboard.

## Portfolio Positioning

This project supports a clear LinkedIn positioning:

> I help teams turn messy data into dashboards, KPI tracking, and business decisions.

It can be used in:

- LinkedIn Featured section
- GitHub pinned repositories
- portfolio website
- job applications
- freelance proposals
- interview walkthroughs

## LinkedIn Content Angles

This one project can become several posts:

- A dashboard is useless if no one owns the KPI.
- Revenue growth can hide a churn problem.
- Data quality is a business risk, not a technical detail.
- Reporting automation should reduce decisions, not just manual work.
- Your GitHub should prove business thinking, not only coding skill.
