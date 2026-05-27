"""
Epic 5: Exploratory Analysis
Queries fct_hospital_penalty_trajectory and fct_hospital_current_performance
to produce key research findings.
"""

from google.cloud import bigquery

client = bigquery.Client(project="data-viz-sandbox-495114")
DATASET = "data-viz-sandbox-495114.cms_raw_historical"


def run_query(label: str, sql: str):
    """Run a query and print results."""
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")
    result = client.query(sql).to_dataframe()
    print(result.to_string(index=False))
    print()
    return result


# ── 5.1.1: Penalty distributions over time ──────────────────────────────

run_query("5.1.1 — Penalty Rate & Severity by Fiscal Year", f"""
    SELECT
        fiscal_year,
        COUNT(*) AS total_hospitals,
        SUM(CASE WHEN is_penalized THEN 1 ELSE 0 END) AS penalized,
        ROUND(100.0 * SUM(CASE WHEN is_penalized THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_penalized,
        ROUND(AVG(penalty_percentage), 3) AS avg_penalty_pct,
        ROUND(MAX(penalty_percentage), 3) AS max_penalty_pct,
        ROUND(AVG(CASE WHEN is_penalized THEN penalty_percentage END), 3) AS avg_penalty_among_penalized
    FROM `{DATASET}.fct_hospital_penalty_trajectory`
    GROUP BY fiscal_year
    ORDER BY fiscal_year
""")


# ── 5.1.2: Penalty persistence rates ────────────────────────────────────

run_query("5.1.2a — Cumulative Penalty Distribution", f"""
    SELECT
        total_years_penalized,
        COUNT(*) AS hospitals,
        ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER(), 1) AS pct_of_total
    FROM `{DATASET}.fct_hospital_current_performance`
    WHERE total_years_tracked = 10
    GROUP BY total_years_penalized
    ORDER BY total_years_penalized
""")

run_query("5.1.2b — Persistence: Penalized FY2019 → Still Penalized FY2025", f"""
    WITH fy2019 AS (
        SELECT facility_id
        FROM `{DATASET}.fct_hospital_penalty_trajectory`
        WHERE fiscal_year = 2019 AND is_penalized
    ),
    fy2025 AS (
        SELECT facility_id, is_penalized
        FROM `{DATASET}.fct_hospital_penalty_trajectory`
        WHERE fiscal_year = 2025
    )
    SELECT
        COUNT(*) AS penalized_2019,
        SUM(CASE WHEN f25.is_penalized THEN 1 ELSE 0 END) AS still_penalized_2025,
        ROUND(100.0 * SUM(CASE WHEN f25.is_penalized THEN 1 ELSE 0 END) / COUNT(*), 1) AS persistence_rate_pct
    FROM fy2019 f19
    JOIN fy2025 f25 USING (facility_id)
""")

run_query("5.1.2c — Year-over-Year Transition Matrix (FY2024 → FY2025)", f"""
    WITH transitions AS (
        SELECT
            prev_year_penalized,
            is_penalized AS current_penalized,
            COUNT(*) AS hospitals
        FROM `{DATASET}.fct_hospital_penalty_trajectory`
        WHERE fiscal_year = 2025 AND prev_year_penalized IS NOT NULL
        GROUP BY prev_year_penalized, is_penalized
    )
    SELECT
        CASE WHEN prev_year_penalized THEN 'Penalized FY2024' ELSE 'Not Penalized FY2024' END AS from_status,
        CASE WHEN current_penalized THEN 'Penalized FY2025' ELSE 'Not Penalized FY2025' END AS to_status,
        hospitals
    FROM transitions
    ORDER BY prev_year_penalized DESC, current_penalized DESC
""")


# ── 5.1.3: Profile chronic penalty recipients ───────────────────────────

run_query("5.1.3a — Chronic (All 10 Years) vs. Others: Hospital Profile", f"""
    SELECT
        penalty_cohort,
        COUNT(*) AS hospitals,
        ROUND(AVG(star_rating), 1) AS avg_star_rating,
        ROUND(AVG(avg_current_err), 3) AS avg_current_err,
        ROUND(AVG(mspb_ratio), 3) AS avg_mspb_ratio,
        ROUND(AVG(complications_worse_than_national), 1) AS avg_complications_worse,
        ROUND(AVG(avg_hac_score), 2) AS avg_hac_score
    FROM `{DATASET}.fct_hospital_current_performance`
    WHERE penalty_cohort IS NOT NULL
    GROUP BY penalty_cohort
    ORDER BY hospitals DESC
""")

run_query("5.1.3b — Chronic Hospitals by Ownership Type", f"""
    SELECT
        ownership_category,
        COUNT(*) AS chronic_hospitals,
        ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER(), 1) AS pct_of_chronic
    FROM `{DATASET}.fct_hospital_current_performance`
    WHERE penalty_cohort = 'chronic'
    GROUP BY ownership_category
    ORDER BY chronic_hospitals DESC
""")

run_query("5.1.3c — Chronic Hospitals by Region", f"""
    SELECT
        census_region,
        COUNT(*) AS chronic_hospitals,
        ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER(), 1) AS pct_of_chronic
    FROM `{DATASET}.fct_hospital_current_performance`
    WHERE penalty_cohort = 'chronic'
    GROUP BY census_region
    ORDER BY chronic_hospitals DESC
""")


# ── 5.1.5: Penalty trajectories for different cohorts ────────────────────

run_query("5.1.5 — Average Penalty Severity by Cohort Over Time", f"""
    SELECT
        t.fiscal_year,
        cp.penalty_cohort,
        COUNT(*) AS hospitals,
        ROUND(AVG(t.penalty_percentage), 3) AS avg_penalty_pct,
        ROUND(AVG(t.avg_excess_readmission_ratio), 4) AS avg_err
    FROM `{DATASET}.fct_hospital_penalty_trajectory` t
    JOIN `{DATASET}.fct_hospital_current_performance` cp USING (facility_id)
    WHERE cp.penalty_cohort IN ('chronic', 'escaper', 'intermittent')
    GROUP BY t.fiscal_year, cp.penalty_cohort
    ORDER BY t.fiscal_year, cp.penalty_cohort
""")


print("\n" + "="*70)
print("  EXPLORATORY ANALYSIS COMPLETE")
print("="*70)
print("""
Key findings to verify:
  1. Penalty rate steady at ~75-80% across all 10 years
  2. ~46% of hospitals penalized all 10 consecutive years
  3. 85% persistence rate (FY2019 penalized → FY2025 still penalized)
  4. Chronic hospitals have worse star ratings, higher ERR, higher spending
  5. Escaper cohort shows declining penalty severity before exiting
""")