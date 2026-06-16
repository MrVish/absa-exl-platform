# Credit Risk PD — Model Development Document (synthetic)

> **Synthetic example** standing in for ABSA's real development documentation,
> so the IDG worked example can run end-to-end. Not a real ABSA model.

## Overview
`credit-risk-pd` estimates the **probability of default (PD)** for retail
customers over a 12-month horizon, returning a continuous PD score in [0, 1] and
a discrete risk band (HIGH / MEDIUM / LOW).

## Methodology
A logistic-regression scorecard over three engineered features. Coefficients
were fit on a historical development sample and validated out-of-time. The model
is intended for **batch** scoring on a monthly cadence.

## Inputs
- `income_band` — discretised income tier (1..5).
- `tenure_months` — months since account opening.
- `delinquencies` — count of 30+ DPD events in the last 12 months (nullable;
  treated as 0 when missing).

## Outputs
- `pd_score` — probability of default (0..1).
- `risk_band` — HIGH (pd ≥ 0.15) / MEDIUM (0.05 ≤ pd < 0.15) / LOW (pd < 0.05).

## Intended use & limitations
Decision support for retail credit review. Not for wholesale exposures. Assumes
inputs are curated upstream in ABSA; the model itself performs no PII handling.

## Owner
ABSA Retail Credit Model Development (synthetic placeholder).
