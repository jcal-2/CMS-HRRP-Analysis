# HRRP at 10 Years: Consolidated Findings

**Project:** CMS Penalty Impact Analysis (HRRP + VBP)
**Author:** Jay Callery
**As of:** 2026-05-23
**Universe:** ~3,000 short-term acute care hospitals tracked across HRRP FY2016 through FY2025 (10 fiscal years), plus a current cross-sectional snapshot from 9 CMS Provider Data API datasets and HCRIS cost reports FY2022 through FY2025.

This document is the canonical findings list. Drafts produced by the `publish` skill should pull headline statistics, methodology language, and policy framing from here.

---

## 1. Cohort definitions

Each hospital is assigned a `penalty_cohort` based on its 10-year HRRP history in `fct_hospital_current_performance`:

| Cohort | Definition | n |
|---|---|---|
| **chronic** | `cumulative_penalties = years_in_dataset` — penalized in every year the hospital appeared in the panel | 1,382 |
| **escaper** | Penalized at least once, but not penalized in FY2025 | 486 |
| **intermittent** | Penalized in some years but not all, and still penalized in FY2025 | (balance) |
| **never_penalized** | Never penalized in the panel | (balance) |

The two cohorts that anchor the analysis are **chronic** and **escaper**. Note that the chronic definition does not require 10 years of data; see Section 5.2 for the distinction between **1,382 chronic** and **1,368 penalized-in-all-10-years**.

---

## 2. Headline findings

### 2.1 Persistence is the dominant pattern
- **1,382 hospitals fall into the chronic cohort** (penalized in every year they appeared in the panel). Of those, **1,368 were penalized in literally all 10 fiscal years FY2016 through FY2025**; the other 14 were penalized in every year they appeared but appeared fewer than 10 times (typically because they opened or closed mid-panel). See Section 5.2 for the distinction.
- Pick the count that matches the framing: use **1,368** for "penalized in all 10 years" and **1,382** for "chronic-cohort hospitals."
- Escapers spent a **median of 6 years (IQR 4 to 8)** penalized before exiting. They were not edge cases who barely qualified; they were entrenched.
- Year-over-year penalty status is highly autocorrelated: in any given year, **approximately 85% of penalized hospitals carry forward into the next year**.

### 2.2 ERR trajectory: small, real, slow improvement in both cohorts
After correcting for a FY2016/2017 staging artifact (the early HRRP files encoded "insufficient cases" as a literal 0.0 in ERR columns rather than NULL; see Section 5), the average excess readmission ratio trajectory by cohort and fiscal year:

| FY | Chronic mean ERR | Escaper mean ERR | Gap |
|----|---:|---:|---:|
| 2016 | 1.027 | 0.982 | 0.045 |
| 2017 | 1.029 | 0.982 | 0.047 |
| 2018 | 1.028 | 0.985 | 0.043 |
| 2019 | 1.027 | 0.985 | 0.043 |
| 2020 | 1.027 | 0.982 | 0.045 |
| 2021 | 1.028 | 0.981 | 0.047 |
| 2022 | 1.025 | 0.981 | 0.044 |
| 2023 | 1.024 | 0.976 | 0.048 |
| 2024 | 1.020 | 0.968 | 0.052 |
| 2025 | 1.020 | 0.960 | 0.060 |

- Linear regression of mean ERR on fiscal year:
  - **Chronic:** slope = −0.00089 per year (R² = 0.72, p = 0.002).
  - **Escaper:** slope = −0.00206 per year (R² = 0.61, p = 0.007).
- Both cohorts are improving, but the absolute change over a decade is small (chronic dropped 0.7 ERR points across 10 years; escapers dropped 2.2 points).
- Escapers were **structurally lower-ERR from FY2016 onward**. They did not arrive at lower ERR through a visible "improvement event"; the 0.04-point gap was present at the start of the panel and only widened modestly.

### 2.3 The escape mechanism is structural, not operational
The HCRIS-linked probe of five candidate mechanisms (n = 1,866 with financials matched; see `analysis/probe_escape_mechanism.py` and `analysis/probe_escape_mechanism_*.csv`) shows escapers and chronics are different **kinds** of hospitals, not chronics that improved:

| Mechanism | Chronic median | Escaper median | Direction | MWU p-value |
|---|---:|---:|:---:|---:|
| H1 Discharges per bed (volume intensity) | 49.4 | 38.6 | chronic > escaper | < 10⁻²⁷ |
| H2 Revenue per discharge | $33,813 | $52,931 | escaper > chronic | < 10⁻⁵⁵ |
| H3 Expense per discharge | $34,856 | $53,990 | escaper > chronic | < 10⁻⁵⁷ |
| H4a FTE per bed (staffing density) | 5.93 | 6.71 | escaper > chronic | < 10⁻⁴ |
| H4b FTE per discharge (labor intensity) | 0.125 | 0.188 | escaper > chronic | < 10⁻⁴⁶ |

- Bed-controlled OLS confirms the per-discharge cohort gaps survive after accounting for hospital size: escaper coefficient t > 17 in all three per-discharge regressions, with R² ≈ 0.16.
- **Interpretation:** escapers are higher-acuity, higher-revenue-per-case, more labor-intensive, lower-occupancy facilities. The signature is consistent with teaching and tertiary referral hospitals; the chronic cohort is consistent with smaller, higher-throughput community hospitals.
- Combined with the ERR trajectory finding, the cohort separation **correlates with** structural and case-mix differences rather than visible clinical-process improvement. The 0.04-point absolute ERR gap and the small year-over-year slope are unlikely to be the sole driver of the binary escape outcome; the peer-grouping methodology introduced in FY2019 plausibly mediates the gap into a discrete penalty / no-penalty classification.

### 2.4 Penalty cap and peer grouping
- Custom dbt tests confirm domain invariants hold across all 10 years:
  - `assert_penalty_cap`: HRRP penalty is capped at 3% (payment factor ≥ 0.97) for FY2016+.
  - `assert_peer_group_only_post_2019`: peer grouping was introduced in FY2019; no pre-2019 row has a peer assignment.
- Pre-2019 rows have null `peer_group_assignment` and `dual_proportion` by design. Analyses that condition on peer group are segmented on the `peer_grouping_era` column.

---

## 3. The compound-penalized cohort (intervention priority tiers)

- **872 hospitals** appear on both the chronic-HRRP list and the VBP TPS bottom quartile in the most recent year of the panel.
- This is the **"compound-penalized cohort"** referred to in commercial framing as **sales tiers** and in academic / regulatory framing as **intervention priority tiers**.
- The full list is exported as `analysis/compound_penalized_hospitals_validated.csv`.

---

## 4. Policy recommendations (paper Section 6)

Four evidence-informed recommendations are carried into publication drafts:

1. **Aggregate penalty cap across HRRP and VBP.** Hospitals that compound penalties across both programs face combined Medicare margin reductions that exceed either program's stated 3% cap; an aggregate cap would prevent program stacking.
2. **Extend peer grouping to VBP.** Peer grouping was added to HRRP in FY2019 and narrowed apparent quality gaps between safety-net hospitals and the rest. VBP has no analogous adjustment.
3. **Reinvestment mandates.** Withheld penalty dollars currently return to the Medicare trust fund. Directing a portion back to penalized facilities for readmission-reduction interventions would convert a withdrawn-resource penalty into an invested-resource one.
4. **Improvement trajectory scoring.** Both cohorts in this analysis improved their ERR over the decade, but the binary penalty / no-penalty outcome did not reward chronic hospitals' slow improvement. Adding an improvement-trajectory dimension would credit direction of travel alongside absolute level.

---

## 5. Methodology notes that affect the trajectory

### 5.1 FY2016/2017 ERR zero-sentinel fix

The findings in Section 2.2 rely on a staging fix shipped in commit `5ba70c71` (2026-05-23). Prior runs of the ERR trajectory showed an anomalous discontinuity at FY2016/2017:

- **Symptom:** mean ERR for escapers appeared to be ~0.71 in FY2016 and ~0.62 in FY2017, then jumped to ~0.98 in FY2018 and held there.
- **Cause:** the FY2016 and FY2017 HRRP supplemental files encode "insufficient cases" as a literal 0.0 in the ERR columns (1,301 zeros in FY2016 AMI alone). FY2018 and later files leave the same condition NULL. The trajectory's averaged ERR was therefore being dragged toward zero, and low-volume facilities (i.e., the escapers, on average) were hit harder.
- **Fix:** each ERR cast in the FY2016 and FY2017 CTEs in `stg_hrrp_penalties.sql` is now wrapped in `nullif(..., 0)`. Real ERR values never come close to 0; the FY2018+ minimum is ~0.7. The treatment is unambiguous.
- **Effect on findings:** the apparent FY2016/2017 "dive and recovery" disappears, and the trajectory becomes a single coherent slow-improvement story for both cohorts. The headline finding (cohort gap is structural, not the result of clinical-process improvement during the panel) is reinforced.

Any publication draft that referenced the prior FY2016/2017 escaper ERR values (0.71 / 0.62) should be updated to the corrected values (0.98 / 0.98).

### 5.2 Chronic cohort: 1,382 vs 1,368

Two persistence counts appear in earlier analysis outputs and they are **both correct** but answer different questions:

| Count | Source | Operational definition |
|---:|---|---|
| **1,382** | `penalty_cohort = 'chronic'` in `fct_hospital_current_performance` | `cumulative_penalties = years_in_dataset` — penalized in every year the hospital appeared, regardless of how many years that was |
| **1,368** | `total_years_penalized = 10` bucket in `analysis/deep_analysis.py` Section 6.3.1 | Penalized in literally all 10 fiscal years FY2016 through FY2025 |

The 14-hospital gap is fully accounted for by chronic hospitals with fewer than 10 years of panel data:

| `total_years_tracked` | n |
|---:|---:|
| 10 | 1,368 |
|  9 |     3 |
|  7 |     4 |
|  6 |     2 |
|  3 |     2 |
|  2 |     2 |
|  1 |     1 |
| **Total chronic** | **1,382** |

These 14 hospitals were penalized in every year they appeared but appeared fewer than 10 times, typically because they opened or closed mid-panel. Whether to count them depends on the question being asked:

- **For "how many hospitals were penalized in every year of the 10-year program," use 1,368.** This is the right framing for the headline "49% penalized in all 10 years" finding, the policy comment on persistence, and any analysis that requires full-panel comparability.
- **For "how many hospitals have a chronic-penalty signature in their current trajectory," use 1,382.** This is the right framing for cohort comparisons (e.g., escapers vs chronic), HCRIS-linked financial probes, and dashboard counts that should not penalize a hospital for having opened in 2019.

The probe in Section 2.3, the ERR trajectory in Section 2.2, and all backtest results use the **1,382** chronic cohort definition. The "49% penalized in all 10 years" headline corresponds to the **1,368** stricter count. Be explicit about which definition is in play when restating either figure.

---

## 6. Data and code references

- **Pipeline:** Python ingestion (`ingestion/`) → BigQuery (project `data-viz-sandbox-495114`) → dbt transforms (`cms_penalty_analysis/`) → analysis scripts (`analysis/`), optionally orchestrated by Dagster (`orchestration/`).
- **Primary marts:**
  - `fct_hospital_penalty_trajectory` — one row per hospital × fiscal year.
  - `fct_hospital_current_performance` — one row per hospital with `penalty_cohort` classification.
  - `fct_hospital_financials` — one row per hospital with most recent HCRIS cost report (now including `total_discharges`).
- **Custom dbt tests:** `assert_penalty_cap`, `assert_peer_group_only_post_2019`, `assert_trajectory_completeness`, `assert_no_duplicate_hospital_years`.
- **Probe outputs:** `analysis/probe_escape_mechanism_two_sample.csv`, `analysis/probe_escape_mechanism_ols.csv`, `analysis/probe_escape_mechanism_err_trajectory.csv`.
- **GitHub repo:** github.com/jcal-2/CMS-HRRP-Analysis.
