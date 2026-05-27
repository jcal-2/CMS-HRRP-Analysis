from google.cloud import bigquery
client = bigquery.Client(project="data-viz-sandbox-495114")

# 1. Penalty persistence: if penalized in FY2019, are you still penalized in FY2025?
print("=== PENALTY PERSISTENCE ===")
q = client.query("""
    WITH fy2019 AS (
        SELECT facility_id, is_penalized AS penalized_2019
        FROM cms_raw_historical.fct_hospital_penalty_trajectory
        WHERE fiscal_year = 2019
    ),
    fy2025 AS (
        SELECT facility_id, is_penalized AS penalized_2025
        FROM cms_raw_historical.fct_hospital_penalty_trajectory
        WHERE fiscal_year = 2025
    )
    SELECT
        penalized_2019,
        penalized_2025,
        COUNT(*) AS hospitals
    FROM fy2019
    JOIN fy2025 USING (facility_id)
    GROUP BY 1, 2
    ORDER BY 1, 2
""")
for row in q:
    print(f"  Penalized 2019: {row.penalized_2019} -> Penalized 2025: {row.penalized_2025} | {row.hospitals} hospitals")

# 2. How many hospitals have been penalized EVERY SINGLE YEAR?
print("\n=== CHRONIC PENALTY HOSPITALS ===")
q2 = client.query("""
    SELECT
        cumulative_penalties,
        COUNT(DISTINCT facility_id) AS hospitals
    FROM cms_raw_historical.fct_hospital_penalty_trajectory
    WHERE fiscal_year = 2025
    GROUP BY 1
    ORDER BY 1
""")
for row in q2:
    print(f"  Penalized {row.cumulative_penalties} of 10 years: {row.hospitals} hospitals")

# 3. Who are the trapped vs escaped?
print("\n=== TRAPPED vs ESCAPED (penalized all 10 years vs improved to 0 penalties) ===")
q3 = client.query("""
    WITH hospital_summary AS (
        SELECT
            facility_id,
            facility_name,
            ownership_category,
            census_region,
            COUNTIF(is_penalized) AS years_penalized,
            ROUND(AVG(penalty_percentage), 4) AS avg_penalty_pct,
            COUNT(*) AS years_in_data
        FROM cms_raw_historical.fct_hospital_penalty_trajectory
        GROUP BY 1, 2, 3, 4
    )
    SELECT
        CASE
            WHEN years_penalized = years_in_data THEN 'Always Penalized'
            WHEN years_penalized = 0 THEN 'Never Penalized'
            ELSE 'Sometimes Penalized'
        END AS cohort,
        COUNT(*) AS hospitals,
        ROUND(AVG(avg_penalty_pct), 4) AS avg_penalty_pct,
        -- Ownership breakdown
        COUNTIF(ownership_category = 'Non-Profit') AS non_profit,
        COUNTIF(ownership_category = 'For-Profit') AS for_profit,
        COUNTIF(ownership_category = 'Government') AS government
    FROM hospital_summary
    GROUP BY 1
    ORDER BY 1
""")
for row in q3:
    print(f"  {row.cohort}: {row.hospitals} hospitals | Avg penalty: {row.avg_penalty_pct}% | NP: {row.non_profit} FP: {row.for_profit} Gov: {row.government}")