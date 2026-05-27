[![CI](https://github.com/jcal-2/CMS-HRRP-Analysis/actions/workflows/ci.yml/badge.svg)](https://github.com/jcal-2/CMS-HRRP-Analysis/actions/workflows/ci.yml)

# Do CMS Financial Penalties Improve Hospital Performance? If not, then what needs to change?

Tracking 3,000+ US hospitals across 10 years of CMS financial penalties (HRRP + VBP) to test whether penalties incentivize improvement or trigger a feedback loop of decline.

## Key Findings

- **49% chronic penalty rate.** Of all hospitals ever penalized under HRRP, nearly half have been penalized in 8+ of 10 fiscal years (FY2016–FY2025) — penalties are persistent, not corrective.
- **123 hospitals can afford to fix it.** A subset of chronically penalized hospitals carry positive operating margins and meaningful net patient revenue, representing **$574.8M** in annual penalty exposure that is financially addressable today.
- **362 at-risk hospitals identified.** A gradient-boosted predictive model flags 362 hospitals trending toward chronic-penalty status, enabling early intervention before they enter the persistent-penalty cohort.

## Published Research

- Medium : [How AI and Public Health Data Can Answer Healthcare’s Hardest Questions](https://medium.com/@jcallery2/how-ai-and-public-health-data-can-answer-healthcares-hardest-questions-bca4430850c4?source=friends_link&sk=b6f3766a7c807c0375ffc00b52f6029b)
- Medium : [123 US Hospitals That Can Afford to Fix Their Readmission Problem But Haven’t](https://medium.com/@jcallery2/123-us-hospitals-that-can-afford-to-fix-their-readmission-problem-but-havent-b2a4827566ab?source=friends_link&sk=5aa2950f49345bfe54c53650b9695110)
- Data : [Qualified-hospitals workbook (Google Sheets)](https://docs.google.com/spreadsheets/d/1BSHM1B93xQfw1dTfqkRMpOUrfiUXj5Oya0ptrNqwHms/edit?usp=sharing)

## Pipeline Architecture

- **Ingestion (Python)** — Pulls 10 fiscal years of HRRP supplemental files, current snapshots from 9 CMS Provider Data API endpoints, VBP Total Performance Score tables, and HCRIS Hospital Cost Reports.
- **Warehouse (BigQuery)** — Raw historical and current datasets land in dedicated schemas.
- **Transform (dbt)** — 12 models (staging + marts) materialize the analytic surface; 13 tests encode domain invariants (HRRP penalty cap, peer-grouping era, no duplicate hospital-years, trajectory completeness).
- **Orchestration (Dagster)** — Full ingestion → dbt build pipeline runs end-to-end in ~23 seconds.
- **Automation (Claude Code)** — 4 specialized agents (data-scout, analyst, policy-engine, publisher) handle ingestion validation, exploratory analysis, scenario modeling, and publication drafting.

## Tech Stack

dbt · Dagster · BigQuery · Python · React + Recharts · GitHub Actions · Claude Code

## Data Sources

- HRRP Supplemental Data Files (FY2016–FY2025)
- VBP Payment Adjustment Tables (FY2016–FY2025)
- HCRIS Hospital Cost Reports (FY2022–FY2025)
- 9 CMS Provider Data API datasets (HCAHPS, readmissions, spending, complications, HAC, timely care, hospital info, unplanned visits, payment/value)

---

**Author:** Jay Callery [LinkedIn](https://www.linkedin.com/in/jay-callery-73820165)
