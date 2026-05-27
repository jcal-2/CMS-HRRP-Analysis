import json
from google.cloud import bigquery
client = bigquery.Client(project="data-viz-sandbox-495114")

# 1. Penalty trend over time
q1 = client.query("""
    SELECT fiscal_year, COUNT(*) as total_hospitals,
        COUNTIF(is_penalized) as penalized,
        ROUND(COUNTIF(is_penalized) / COUNT(*) * 100, 1) as pct_penalized,
        ROUND(AVG(penalty_percentage) * 100, 2) as avg_penalty_pct,
        ROUND(AVG(avg_excess_readmission_ratio), 4) as avg_err
    FROM cms_raw_historical.fct_hospital_penalty_trajectory
    GROUP BY 1 ORDER BY 1
""")
trend_data = [dict(row) for row in q1]
print(f"Trend data: {len(trend_data)} rows")

# 2. Cohort trajectories
q2 = client.query("""
    WITH cohorts AS (
        SELECT facility_id, COUNTIF(is_penalized) as yrs, COUNT(*) as total
        FROM cms_raw_historical.fct_hospital_penalty_trajectory GROUP BY 1
    ),
    labeled AS (
        SELECT facility_id,
            CASE WHEN yrs = total THEN 'Always Penalized'
                 WHEN yrs = 0 THEN 'Never Penalized'
                 WHEN yrs >= 8 THEN 'Almost Always'
                 ELSE 'Sometimes' END AS cohort
        FROM cohorts
    )
    SELECT l.cohort, t.fiscal_year,
        COUNT(*) as hospitals,
        ROUND(AVG(t.penalty_percentage) * 100, 2) as avg_penalty,
        ROUND(AVG(t.avg_excess_readmission_ratio), 4) as avg_err
    FROM cms_raw_historical.fct_hospital_penalty_trajectory t
    JOIN labeled l ON t.facility_id = l.facility_id
    WHERE t.fiscal_year >= 2018
    GROUP BY 1, 2 ORDER BY 1, 2
""")
cohort_data = [dict(row) for row in q2]
print(f"Cohort data: {len(cohort_data)} rows")

# 3. Ownership breakdown
q3 = client.query("""
    WITH cohorts AS (
        SELECT facility_id, COUNTIF(is_penalized) as yrs, COUNT(*) as total
        FROM cms_raw_historical.fct_hospital_penalty_trajectory GROUP BY 1
    ),
    labeled AS (
        SELECT facility_id,
            CASE WHEN yrs = total THEN 'Always'
                 WHEN yrs = 0 THEN 'Never'
                 ELSE 'Sometimes' END AS cohort
        FROM cohorts
    )
    SELECT t.ownership_category, l.cohort, COUNT(DISTINCT t.facility_id) as hospitals
    FROM cms_raw_historical.fct_hospital_penalty_trajectory t
    JOIN labeled l ON t.facility_id = l.facility_id
    WHERE t.fiscal_year = 2025 AND t.ownership_category IS NOT NULL
    GROUP BY 1, 2 ORDER BY 1, 2
""")
ownership_data = [dict(row) for row in q3]
print(f"Ownership data: {len(ownership_data)} rows")

# 4. Regional patterns
q4 = client.query("""
    SELECT census_region, fiscal_year,
        ROUND(COUNTIF(is_penalized) / COUNT(*) * 100, 1) as pct_penalized,
        ROUND(AVG(penalty_percentage) * 100, 2) as avg_penalty
    FROM cms_raw_historical.fct_hospital_penalty_trajectory
    WHERE census_region IS NOT NULL AND census_region != 'Other'
    GROUP BY 1, 2 ORDER BY 1, 2
""")
regional_data = [dict(row) for row in q4]
print(f"Regional data: {len(regional_data)} rows")

# 5. Persistence matrix
q5 = client.query("""
    WITH hospital_years AS (
        SELECT facility_id, fiscal_year, is_penalized,
            LEAD(is_penalized) OVER (PARTITION BY facility_id ORDER BY fiscal_year) as next_year_penalized,
            LEAD(fiscal_year) OVER (PARTITION BY facility_id ORDER BY fiscal_year) as next_fiscal_year
        FROM cms_raw_historical.fct_hospital_penalty_trajectory
    )
    SELECT fiscal_year as from_year, next_fiscal_year as to_year,
        COUNTIF(is_penalized AND next_year_penalized) as stayed_penalized,
        COUNTIF(is_penalized AND NOT next_year_penalized) as escaped,
        COUNTIF(NOT is_penalized AND next_year_penalized) as entered,
        COUNTIF(NOT is_penalized AND NOT next_year_penalized) as stayed_free
    FROM hospital_years
    WHERE next_fiscal_year IS NOT NULL
    GROUP BY 1, 2 ORDER BY 1
""")
persistence_data = [dict(row) for row in q5]
print(f"Persistence data: {len(persistence_data)} rows")

# Save all to JSON
all_data = {
    "trend": trend_data,
    "cohorts": cohort_data,
    "ownership": ownership_data,
    "regional": regional_data,
    "persistence": persistence_data
}

with open("dashboard_data.json", "w") as f:
    json.dump(all_data, f, indent=2, default=str)

print("\nAll data exported to dashboard_data.json")