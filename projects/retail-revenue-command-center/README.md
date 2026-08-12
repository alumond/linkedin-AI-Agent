# Retail Revenue & Operations Command Center

This flagship portfolio project is a Power BI-style executive dashboard built for a fast-growing retail business.

It is designed to show one thing clearly: I can turn a multi-dimensional business dataset into revenue, customer, margin, and operations decisions.

## Business Problem

A retail leadership team needs a command center that brings commercial and operational signals into one view.

The team wants to know:

- Is revenue growth supported by healthy profit?
- Which product categories are carrying performance?
- Which channels drive the most value?
- Are new customers turning into repeat customers?
- Where are returns, fulfillment delays, and stockout risk putting margin under pressure?
- What should management act on this week?

## Dataset

The builder script generates a realistic synthetic dataset with 2,160 rows across:

- 18 months
- 5 regions
- 4 sales channels
- 6 product categories
- campaign types
- revenue, cost, gross profit, marketing spend
- orders, returns, support tickets
- new customers, repeat customers, churned customers
- fulfillment delay, stockout risk, satisfaction, and data quality flags

Generated file:

`data/retail_operations_kpis.csv`

## Dashboard Sections

- Executive KPI cards for revenue, gross profit, orders, customers, and repeat rate
- Revenue and gross profit trend
- Product category revenue ranking
- Channel mix
- Acquisition vs retention view
- Margin risk and returns analysis
- Regional performance grid
- Executive insight cards with recommended actions

## Tools Used

- Python standard library
- CSV
- JSON
- HTML
- CSS
- SVG

The project has no external dependency. It is easy to run locally, upload to GitHub, or host as a static portfolio artifact.

## How To Run

From this project folder:

```bash
python3 scripts/build_dashboard.py
```

Outputs:

- `data/retail_operations_kpis.csv`
- `outputs/dashboard.html`
- `outputs/linkedin_landscape.html`
- `outputs/kpi_summary.json`

Open `outputs/dashboard.html` in a browser to view the dashboard.
Open `outputs/linkedin_landscape.html` when you want a 16:9 screenshot-ready version for LinkedIn.

## Portfolio Positioning

Use this project to support this LinkedIn positioning:

> Data Analyst for Business Growth | Dashboards | KPI Reporting | Decision Support | Python

This project proves:

- dashboard design judgment
- business KPI thinking
- data storytelling
- synthetic dataset design
- executive reporting
- Python automation

## LinkedIn Content Angles

- A dashboard should tell leadership where money is leaking.
- Revenue growth can still hide margin pressure.
- Repeat customers are a better signal than surface-level traffic.
- Returns and fulfillment delays belong in the same conversation as revenue.
- A strong GitHub project should show business judgment, not only code.
