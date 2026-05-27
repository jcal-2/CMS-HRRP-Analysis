from google.cloud import bigquery
client = bigquery.Client(project="data-viz-sandbox-495114")

print("=== PEER GROUPING EFFECT ON HIGH DUAL-ELIGIBLE HOSPITALS ===")
q = client.query("""
    WITH hospital_eras AS (
        SELECT
            facility_id,
            CASE 
                WHEN dual_proportion >= 0.40 THEN 'High Dual 40+'
                WHEN dual_proportion >= 0.20 THEN 'Medium Dual 20-40'
                ELSE 'Low Dual under 20'
            END AS dual_category,
            CASE WHEN fiscal_year < 2019 THEN 'Pre' ELSE 'Post' END AS era,
            AVG(penalty_percentage) AS avg_penalty
        FROM cms_raw_historical.fct_hospital_penalty_trajectory
        WHERE dual_proportion IS NOT NULL
        GROUP BY 1, 2, 3
    )
    SELECT dual_category, era, COUNT(*) AS hospitals,
        ROUND(AVG(avg_penalty), 4) AS avg_penalty_pct
    FROM hospital_eras GROUP BY 1, 2 ORDER BY 1, 2
""")
for row in q:
    print(f"  {row.dual_category} | {row.era} | {row.hospitals} | Penalty: {row.avg_penalty_pct}%")

print("\n=== TRAPPED vs ESCAPED TRAJECTORY ===")
q2 = client.query("""
    WITH cohorts AS (
        SELECT facility_id, COUNTIF(is_penalized) AS yrs_pen, COUNT(*) AS total
        FROM cms_raw_historical.fct_hospital_penalty_trajectory GROUP BY 1
    ),
    labeled AS (
        SELECT facility_id,
            CASE WHEN yrs_pen = total THEN 'Always'
                 WHEN yrs_pen = 0 THEN 'Never'
                 WHEN yrs_pen >= 8 THEN 'Almost Always'
                 ELSE 'Sometimes' END AS cohort
        FROM cohorts
    )
    SELECT l.cohort, t.fiscal_year, COUNT(*) AS hospitals,
        ROUND(AVG(t.penalty_percentage), 4) AS avg_penalty,
        ROUND(AVG(t.avg_excess_readmission_ratio), 4) AS avg_err
    FROM cms_raw_historical.fct_hospital_penalty_trajectory t
    JOIN labeled l ON t.facility_id = l.facility_id
    GROUP BY 1, 2 ORDER BY 1, 2
""")
current = None
for row in q2:
    if row.cohort != current:
        print(f"\n  --- {row.cohort} ---")
        current = row.cohort
    print(f"  FY{row.fiscal_year}: {row.hospitals} | Penalty: {row.avg_penalty}% | ERR: {row.avg_err}")

print("\n=== OWNERSHIP x PENALTY COHORT (FY2025) ===")
q3 = client.query("""
    WITH cohorts AS (
        SELECT facility_id, COUNTIF(is_penalized) AS yrs_pen, COUNT(*) AS total
        FROM cms_raw_historical.fct_hospital_penalty_trajectory GROUP BY 1
    ),
    labeled AS (
        SELECT facility_id,
            CASE WHEN yrs_pen = total THEN 'Always'
                 WHEN yrs_pen = 0 THEN 'Never'
                 ELSE 'Sometimes' END AS cohort
        FROM cohorts
    )
    SELECT t.ownership_category, l.cohort, COUNT(DISTINCT t.facility_id) AS hospitals
    FROM cms_raw_historical.fct_hospital_penalty_trajectory t
    JOIN labeled l ON t.facility_id = l.facility_id
    WHERE t.fiscal_year = 2025
    GROUP BY 1, 2 ORDER BY 1, 2
""")
for row in q3:
    print(f"  {row.ownership_category} | {row.cohort} | {row.hospitals}")

print("\n=== REGIONAL PATTERNS (FY2025) ===")
q4 = client.query("""
    SELECT census_region, COUNT(*) AS hospitals,
        COUNTIF(is_penalized) AS penalized,
        ROUND(COUNTIF(is_penalized) / COUNT(*) * 100, 1) AS pct_penalized,
        ROUND(AVG(penalty_percentage), 4) AS avg_penalty
    FROM cms_raw_historical.fct_hospital_penalty_trajectory
    WHERE fiscal_year = 2025 AND census_region IS NOT NULL
    GROUP BY 1 ORDER BY pct_penalized DESC
""")
for row in q4:
    print(f"  {row.census_region}: {row.penalized}/{row.hospitals} penalized ({row.pct_penalized}%) | Avg: {row.avg_penalty}%")