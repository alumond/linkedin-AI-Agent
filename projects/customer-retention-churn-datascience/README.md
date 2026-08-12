# Customer Retention + Churn Forecast Data Science Project

This flagship project demonstrates practical **data science** instead of just dashboarding:

- synthetic customer-level data generation
- churn label engineering
- logistic regression training from first principles (no external ML libraries)
- model evaluation (precision, recall, F1)
- cohort risk scoring
- short-term churn projection and revenue-at-risk estimate
- executive-ready HTML narrative and artifact pack

## Business question

The team is growing customers, but growth still needs to be tested against retention quality.

**Can we identify high-risk accounts early and quantify what churn could cost the business next quarter?**

## Data design

The dataset is synthetic and deterministic for portfolio demonstration.

Fields:

- `customer_id`
- `month`
- `segment`
- `acquisition_channel`
- `tenure_months`
- `monthly_active_minutes`
- `support_tickets`
- `feature_adoption`
- `satisfaction_score`
- `monthly_revenue`
- `marketing_influence`
- `churned`

## Model approach

1. Generate 24 months of customer lifecycle behavior.
2. Label each customer-month with churn outcome (`churned`).
3. Split chronologically:
   - first 70% for training
   - last 30% for holdout
4. Fit a logistic regression model with gradient descent.
5. Evaluate on holdout and produce precision/recall/F1.
6. Score every customer-month and rank by churn risk.

## Outputs

Running the script produces:

- `data/customer_retention_kpis.csv`
- `outputs/churn_summary.json`
- `outputs/churn_case_study.html`
- `outputs/churn_risk_snapshot.png`

## Run

```bash
python3 scripts/build_churn_datascience_pack.py
```

Open the HTML and review the PNG/JSON artifacts:

- `outputs/churn_case_study.html`
- `outputs/churn_risk_snapshot.png`
- `outputs/churn_summary.json`

## Why this is flagship-friendly

It shows a repeatable data science workflow:
- not just reporting
- model-first thinking
- quantified business risk and recommendation logic
- portfolio-ready reproducibility via one script
