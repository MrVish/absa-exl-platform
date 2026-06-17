# Credit Risk PD — Model Development Document (synthetic)

> **Synthetic example** standing in for ABSA's real development documentation,
> so the IDG worked example can run end-to-end. Structured to mirror ABSA's
> agreed Model Development Document table of contents. Not a real ABSA model and
> contains no real data.

## 1. Overview

### 1.1 Executive Summary
`credit-risk-pd` estimates the **probability of default (PD)** for retail
mortgage customers over a 12-month horizon, returning a continuous PD score in
[0, 1] and a discrete risk band (HIGH / MEDIUM / LOW).

### 1.2 Model Classification
Behavioural application scorecard; material retail-credit model under ABSA's
model-risk classification. Governed per GMRMG.

### 1.3 Background and motivation
Replaces an ageing scorecard with degraded discrimination on recent vintages.

### 1.4 Model governance and change policy
Changes follow CAB/IVU approval; re-development triggers a new version.

### 1.5 Modelling standards and policies
Built to ABSA modelling standards (documentation, validation, monitoring).

### 1.6 Model Description
A logistic-regression scorecard over engineered characteristics, calibrated to
the central tendency of the development sample.

### 1.7 Model rationalisation history
v1.0.0 is the initial production-candidate; supersedes legacy scorecard SC-07.

## 2. Portfolio Overview

### 2.1 Product Information, Features and Target Markets
Retail secured lending (structured mortgages); South African retail book.

### 2.2 External Legislative Changes
Subject to the National Credit Act and POPIA; no material legislative change in
the development window.

## 3. Data Landscape and Data Preparation

### 3.1 Data Sources
Curated application + bureau + account-performance marts inside ABSA.

### 3.2 Variable Definitions
- `income_band` — discretised income tier (1..5).
- `tenure_months` — months since account opening.
- `delinquencies` — count of 30+ DPD events in the last 12 months (nullable;
  treated as 0 when missing).

### 3.3 Data Flow
Model-ready, de-identified extracts are prepared in ABSA and handed to the
hosting platform; raw PII never leaves ABSA.

### 3.4 Default Definition
90+ days past due within the 12-month outcome window (Basel-aligned).

### 3.5 Account level versus Customer level Treatment
Scored at account level; customer-level roll-up handled downstream.

### 3.6 Exclusions
Staff accounts, deceased, legal/recoveries, and <3-month-on-book are excluded.

## 4. Model Development

### 4.1 Methodology
Logistic-regression scorecard; weights-of-evidence binning then stepwise
selection, validated out-of-time.

### 4.2 Development Period
Development sample drawn over a multi-year observation window with a 12-month
outcome.

### 4.3 Investigate Multiple Models / Segmentation
A single segment was retained after segmentation analysis (Appendix A).

### 4.4 Sample Design
Stratified development / hold-out split with out-of-time validation.

### 4.5 Univariate Analysis
Characteristic-level information value and monotonicity screening.

### 4.6 Multivariate Analysis
Stepwise logistic regression with stability and multicollinearity checks.

## 5. Final Scorecard

### 5.1 Final Scorecard Variables
Three retained characteristics (income band, tenure, delinquencies) with fitted
points.

### 5.2 Correlation among Final Variables
Pairwise correlation within accepted tolerance.

### 5.3 Multicollinearity in Final Variables
VIF within threshold for all retained variables.

## 6. Model Performance

### 6.1 Model Discrimination
Gini / AUC on hold-out and out-of-time samples meet the acceptance threshold.

### 6.2 Variable Stability
Characteristic stability (PSI) within tolerance across recent vintages.

### 6.3 Score Stability Distribution
Score distribution stable vs the development population.

### 6.4 Benchmarking against the current scorecard
Outperforms the legacy scorecard on discrimination and stability.

## 7. Model Strengths and Weaknesses

### 7.1 Strengths of the Approach
Transparent, monotonic, well-understood scorecard; easy to monitor.

### 7.2 Weaknesses of the Approach
Linear in WoE space; limited capture of interaction effects.

## 8. Post Development

### 8.1 Model Monitoring and Tracking Framework
Monthly PSI, score-distribution and outcome tracking with defined triggers.

### 8.2 Proposed Tracking metrics
PSI per characteristic, score PSI, override and approval rates.

## 9. Conservatism
A conservative calibration margin is applied pending sufficient outcome data.

## 10. Implementation
Intended for **monthly batch** scoring. Inputs are curated upstream in ABSA;
the model itself performs no PII handling.

## 11. References
Internal ABSA modelling standards, GMRMG, and the Definition of Default policy.

## Appendix A: Segmentation results
Segmentation analysis supporting the single-segment decision.

## Appendix B: Variable Stability
Per-characteristic stability tables across vintages.

## Appendix C: Structured Mortgages – Definition of Default document
Reference to the governing default-definition policy.

## Appendix D: Development Code
The development scoring code handed to EXL for productionisation.

## Owner
ABSA Retail Credit Model Development (synthetic placeholder).
